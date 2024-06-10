import logging
import sys
from threading import Thread

import docker
from flask import g, request
from flask_restful import Api
from http import HTTPStatus

from vantage6.algorithm.store import db
from vantage6.algorithm.store.model.rule import Operation
from vantage6.common import logger_name
from vantage6.algorithm.store.model.ui_visualization import UIVisualization
from vantage6.algorithm.store.resource.schema.input_schema import (
    AlgorithmInputSchema,
    AlgorithmPatchInputSchema,
)
from vantage6.algorithm.store.resource.schema.output_schema import AlgorithmOutputSchema
from vantage6.algorithm.store.model.algorithm import Algorithm as db_Algorithm
from vantage6.algorithm.store.model.argument import Argument
from vantage6.algorithm.store.model.database import Database
from vantage6.algorithm.store.model.function import Function
from vantage6.algorithm.store.resource import (
    with_permission,
    with_permission_to_view_algorithms,
)

# TODO move to common / refactor
from vantage6.algorithm.store.resource import AlgorithmStoreResources
from vantage6.algorithm.store.permission import (
    PermissionManager,
    Operation as P,
)
from vantage6.backend.common.resource.pagination import Pagination
from vantage6.common.docker.addons import is_hex_digest, split_tag_from_image

module_name = logger_name(__name__)
log = logging.getLogger(module_name)


def setup(api: Api, api_base: str, services: dict) -> None:
    """
    Setup the version resource.

    Parameters
    ----------
    api : Api
        Flask restful api instance
    api_base : str
        Base url of the api
    services : dict
        Dictionary with services required for the resource endpoints
    """
    path = "/".join([api_base, module_name])
    log.info('Setting up "%s" and subdirectories', path)

    api.add_resource(
        Algorithms,
        path,
        endpoint="algorithm_without_id",
        methods=("GET", "POST"),
        resource_class_kwargs=services,
    )

    api.add_resource(
        Algorithm,
        path + "/<int:id>",
        endpoint="algorithm_with_id",
        methods=("GET", "DELETE", "PATCH"),
        resource_class_kwargs=services,
    )


algorithm_input_post_schema = AlgorithmInputSchema()
algorithm_input_patch_schema = AlgorithmPatchInputSchema()
algorithm_output_schema = AlgorithmOutputSchema()


# ------------------------------------------------------------------------------
# Permissions
# ------------------------------------------------------------------------------
def permissions(permission_mgr: PermissionManager) -> None:
    """
    Define the permissions for this resource.

    Parameters
    ----------
    permissions : PermissionManager
        Permission manager instance to which permissions are added
    """
    add = permission_mgr.appender(module_name)
    add(P.VIEW, description="View any algorithm")
    add(P.CREATE, description="Create a new algorithm")
    add(P.EDIT, description="Edit any algorithm")
    add(P.DELETE, description="Delete any algorithm")
    add(P.REVIEW, description="Edit some fields of the algorithm")


# ------------------------------------------------------------------------------
# Resources / API's
# ------------------------------------------------------------------------------


class AlgorithmBaseResource(AlgorithmStoreResources):
    """Base class for the algorithm resource"""

    def _save_image_digest(self, algorithm_id: int, image_name: str) -> None:
        """
        Get the sha256 of the image and store it in the database.

        This method is run in a separate thread to prevent the request from taking too
        long. Do NOT call this method from the main thread!

        Parameters
        ----------
        algorithm : int
            ID of the algorithm in the database
        image : str
            Image url
        """
        # split image and tag
        try:
            image_wo_tag, tag = split_tag_from_image(image_name)
        except ValueError as e:
            log.exception(
                "Could not determine digest for algorithm %s: %s", algorithm_id, e
            )
            sys.exit()

        if is_hex_digest(tag):
            self._store_digest(image_wo_tag, tag, algorithm_id)

        # if digest is not part of the tag, pull the image and retrieve the digest from
        # there
        client = docker.from_env()
        try:
            image = client.images.get(image_name)
        except docker.errors.ImageNotFound:
            log.exception("Image %s not found! Cannot store digest.", image_name)
            sys.exit()

        # get the digest and store it
        digest = image.attrs["RepoDigests"][0].split("@")[1]
        self._store_digest(image_wo_tag, digest, algorithm_id)
        sys.exit()

    def _store_digest(self, image_wo_tag: str, digest: str, algorithm_id: int) -> None:
        """
        Store the digest in the database.

        Parameters
        ----------
        image_wo_tag : str
            Image url without the tag
        digest : str
            Digest of the image
        algorithm_id : int
            ID of the algorithm in the database
        """
        algorithm = db_Algorithm.get(algorithm_id)
        log.info("Storing digest %s for algorithm %s", digest, algorithm.id)
        algorithm.image = image_wo_tag
        algorithm.digest = digest
        algorithm.save()


class Algorithms(AlgorithmBaseResource):
    """Resource for /algorithm"""

    @with_permission_to_view_algorithms(module_name, Operation.VIEW)
    def get(self):
        """List algorithms
        ---
        description: Return a list of algorithms

        parameters:
          - in: query
            name: name
            schema:
              type: string
            description: Filter on algorithm name using the SQL operator LIKE.
          - in: query
            name: description
            schema:
              type: string
            description: Filter on algorithm description using the SQL operator
              LIKE.
          - in: query
            name: image
            schema:
              type: string
            description: Filter on algorithm image using the SQL operator LIKE.
          - in: query
            name: partitioning
            schema:
              type: string
            description: Filter on algorithm partitioning. Can be 'horizontal'
              or 'vertical'.
          - in: query
            name: vantage6_version
            schema:
              type: string
            description: Filter on algorithm vantage6 version using the SQL
              operator LIKE.

        responses:
          200:
            description: OK
          400:
            description: Invalid input
          401:
            description: Unauthorized

        security:
          - bearerAuth: []

        tags: ["Algorithm"]
        """
        q = g.session.query(db_Algorithm)

        # filter on properties
        for field in [
            "name",
            "description",
            "image",
            "partitioning",
            "vantage6_version",
        ]:
            if (value := request.args.get(field)) is not None:
                q = q.filter(getattr(db_Algorithm, field).like(value))

        # paginate results
        try:
            page = Pagination.from_query(q, request, db.Algorithm)
        except (ValueError, AttributeError) as e:
            return {"msg": str(e)}, HTTPStatus.BAD_REQUEST

        # model serialization
        return self.response(page, algorithm_output_schema)

    @with_permission(module_name, Operation.CREATE)
    def post(self):
        """Create new algorithm
        ---
        description: >-
          Create a new algorithm. The algorithm is not yet active. It is
          created in a draft state. The algorithm can be activated by
          changing the status to 'active'.

        requestBody:
          content:
            application/json:
              schema:
                properties:
                  name:
                    type: string
                    description: Name of the algorithm
                  description:
                    type: string
                    description: Description of the algorithm
                  image:
                    type: string
                    description: Docker image URL
                  partitioning:
                    type: string
                    description: Type of partitioning. Can be 'horizontal' or
                      'vertical'
                  vantage6_version:
                    type: string
                    description: Version of vantage6 that the algorithm is
                      built with / for
                  functions:
                    type: array
                    description: List of functions that are available in the
                      algorithm
                    items:
                      properties:
                        name:
                          type: string
                          description: Name of the function
                        description:
                          type: string
                          description: Description of the function
                        type:
                          type: string
                          description: Type of function. Can be 'central' or
                            'federated'
                        databases:
                          type: array
                          description: List of databases that this function
                            uses
                          items:
                            properties:
                              name:
                                type: string
                                description: Name of the database in the
                                  function
                              description:
                                type: string
                                description: Description of the database
                        arguments:
                          type: array
                          description: List of arguments that this function
                            uses
                          items:
                            properties:
                              name:
                                type: string
                                description: Name of the argument in the
                                  function
                              description:
                                type: string
                                description: Description of the argument
                              type:
                                type: string
                                description: Type of argument. Can be 'string',
                                  'integer', 'float', 'boolean', 'json',
                                  'column', 'organizations' or 'organization'
                        ui_visualizations:
                          type: array
                          description: List of visualizations that are available in
                            the algorithm
                          items:
                            properties:
                              name:
                                type: string
                                description: Name of the visualization
                              description:
                                type: string
                                description: Description of the visualization
                              type:
                                type: string
                                description: Type of visualization.
                              schema:
                                type: object
                                description: Schema that describes the visualization

        responses:
          201:
            description: Algorithm created successfully
          400:
            description: Invalid input
          401:
            description: Unauthorized

        security:
          - bearerAuth: []

        tags: ["Algorithm"]
        """
        data = request.get_json()

        # validate the request body
        errors = algorithm_input_post_schema.validate(data)
        if errors:
            return {
                "msg": "Request body is incorrect",
                "errors": errors,
            }, HTTPStatus.BAD_REQUEST

        # create the algorithm
        algorithm = db_Algorithm(
            name=data["name"],
            description=data.get("description", ""),
            image=data["image"],
            partitioning=data["partitioning"],
            vantage6_version=data["vantage6_version"],
        )
        algorithm.save()

        # create the algorithm's subresources
        for function in data["functions"]:
            # create the function
            func = Function(
                name=function["name"],
                description=function.get("description", ""),
                type_=function["type"],
                algorithm_id=algorithm.id,
            )
            func.save()
            # create the arguments
            for argument in function.get("arguments", []):
                arg = Argument(
                    name=argument["name"],
                    description=argument.get("description", ""),
                    type_=argument["type"],
                    function_id=func.id,
                )
                arg.save()
            # create the databases
            for database in function.get("databases", []):
                db_ = Database(
                    name=database["name"],
                    description=database.get("description", ""),
                    function_id=func.id,
                )
                db_.save()
            # create the visualizations
            for visualization in function.get("ui_visualizations", []):
                vis = UIVisualization(
                    name=visualization["name"],
                    description=visualization.get("description", ""),
                    type_=visualization["type"],
                    schema=visualization.get("schema", {}),
                    function_id=func.id,
                )
                vis.save()

        # start a parallel process to retrieve and store the digest of the image. This
        # is done in a separate process to prevent the request from taking too long.
        thread = Thread(
            target=self._save_image_digest,
            args=(algorithm.id, data["image"]),
        )
        thread.start()

        return algorithm_output_schema.dump(algorithm, many=False), HTTPStatus.CREATED


class Algorithm(AlgorithmBaseResource):
    """Resource for /algorithm/<id>"""

    @with_permission_to_view_algorithms(module_name, Operation.VIEW)
    def get(self, id):
        """Get algorithm
        ---
        description: Return an algorithm specified by ID.

        parameters:
          - in: path
            name: id
            schema:
              type: integer
            description: ID of the algorithm

        responses:
          200:
            description: OK
          401:
            description: Unauthorized
          404:
            description: Algorithm not found

        security:
          - bearerAuth: []

        tags: ["Algorithm"]
        """
        algorithm = db_Algorithm.get(id)
        if not algorithm:
            return {"msg": "Algorithm not found"}, HTTPStatus.NOT_FOUND

        return algorithm_output_schema.dump(algorithm, many=False), HTTPStatus.OK

    @with_permission(module_name, Operation.DELETE)
    def delete(self, id):
        """Delete algorithm
        ---
        description: Delete an algorithm specified by ID.

        parameters:
          - in: path
            name: id
            schema:
              type: integer
            description: ID of the algorithm

        responses:
          200:
            description: OK
          401:
            description: Unauthorized
          404:
            description: Algorithm not found

        security:
          - bearerAuth: []

        tags: ["Algorithm"]
        """
        algorithm = db_Algorithm.get(id)
        if not algorithm:
            return {"msg": "Algorithm not found"}, HTTPStatus.NOT_FOUND

        # delete all subresources and finally the algorithm itself
        for function in algorithm.functions:
            for database in function.databases:
                database.delete()
            for argument in function.arguments:
                argument.delete()
            for visualization in function.ui_visualizations:
                visualization.delete()
            function.delete()
        algorithm.delete()

        return {"msg": f"Algorithm id={id} was successfully deleted"}, HTTPStatus.OK

    @with_permission(module_name, Operation.EDIT)
    def patch(self, id):
        """Patch algorithm
        ---
        description: Modify an algorithm specified by ID.

        parameters:
          - in: path
            name: id
            schema:
              type: integer
              minimum: 1
            description: Algorithm id
            required: tr

        requestBody:
          content:
            application/json:
              schema:
                properties:
                  name:
                    type: string
                    description: Name of the algorithm
                  description:
                    type: string
                    description: Description of the algorithm
                  image:
                    type: string
                    description: Docker image URL
                  partitioning:
                    type: string
                    description: Type of partitioning. Can be 'horizontal' or
                      'vertical'
                  vantage6_version:
                    type: string
                    description: Version of vantage6 that the algorithm is
                      built with / for
                  functions:
                    type: array
                    description: List of functions that are available in the
                      algorithm
                    items:
                      properties:
                        name:
                          type: string
                          description: Name of the function
                        description:
                          type: string
                          description: Description of the function
                        type:
                          type: string
                          description: Type of function. Can be 'central' or
                            'federated'
                        databases:
                          type: array
                          description: List of databases that this function
                            uses
                          items:
                            properties:
                              name:
                                type: string
                                description: Name of the database in the
                                  function
                              description:
                                type: string
                                description: Description of the database
                        arguments:
                          type: array
                          description: List of arguments that this function
                            uses
                          items:
                            properties:
                              name:
                                type: string
                                description: Name of the argument in the
                                  function
                              description:
                                type: string
                                description: Description of the argument
                              type:
                                type: string
                                description: Type of argument. Can be 'string',
                                  'integer', 'float', 'boolean', 'json',
                                  'column', 'organizations' or 'organization'
                        ui_visualizations:
                          type: array
                          description: List of visualizations that are available in
                            the algorithm
                          items:
                            properties:
                              name:
                                type: string
                                description: Name of the visualization
                              description:
                                type: string
                                description: Description of the visualization
                              type:
                                type: string
                                description: Type of visualization.
                              schema:
                                type: object
                                description: Schema that describes the visualization.
                  refresh_digest:
                    type: boolean
                    description: If true, the digest of the image will be refreshed
                      and stored in the database. Note that this is also done whenever
                      the image is changed.

        responses:
          201:
            description: Algorithm created successfully
          400:
            description: Invalid input
          401:
            description: Unauthorized

        security:
          - bearerAuth: []

        tags: ["Algorithm"]
        """
        algorithm = db_Algorithm.get(id)
        if not algorithm:
            return {"msg": "Algorithm not found"}, HTTPStatus.NOT_FOUND

        data = request.get_json()

        # validate the request body
        errors = algorithm_input_patch_schema.validate(data, partial=True)
        if errors:
            return {
                "msg": "Request body is incorrect",
                "errors": errors,
            }, HTTPStatus.BAD_REQUEST

        fields = ["name", "description", "partitioning", "vantage6_version"]
        for field in fields:
            if field in data and data.get(field) is not None:
                setattr(algorithm, field, data.get(field))

        image = data.get("image")
        # If image is updated or refresh_digest is set to True, update the digest of the
        # image in a separate thread. Doing this in the same thread would take too long
        # because docker image needs to be pulled
        if image != algorithm.image or data.get("refresh_digest", False):
            thread = Thread(
                target=self._save_image_digest,
                args=(algorithm.id, image if image is not None else algorithm.image),
            )
            thread.start()
        # don't forget to also update the image itself
        if image is not None:
            algorithm.image = image

        if (functions := data.get("functions")) is not None:
            for function in algorithm.functions:
                for argument in function.arguments:
                    argument.delete()
                for db_ in function.databases:
                    db_.delete()
                for visualization in function.ui_visualizations:
                    visualization.delete()
                function.delete()

            for new_function in functions:
                func = Function(
                    name=new_function["name"],
                    description=new_function.get("description", ""),
                    type_=new_function["type"],
                    algorithm_id=id,
                )
                func.save()

                for argument in new_function.get("arguments", []):
                    arg = Argument(
                        name=argument["name"],
                        description=argument.get("description", ""),
                        type_=argument["type"],
                        function_id=func.id,
                    )
                    arg.save()
                for database in new_function.get("databases", []):
                    db = Database(
                        name=database["name"],
                        description=database.get("description", ""),
                        function_id=func.id,
                    )
                    db.save()
                for visualization in new_function.get("ui_visualizations", []):
                    vis = UIVisualization(
                        name=visualization["name"],
                        description=visualization.get("description", ""),
                        type_=visualization["type"],
                        schema=visualization.get("schema", {}),
                        function_id=func.id,
                    )
                    vis.save()

        algorithm.save()

        return algorithm_output_schema.dump(algorithm, many=False), HTTPStatus.OK
