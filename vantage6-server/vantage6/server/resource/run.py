# -*- coding: utf-8 -*-
import logging
from typing import Union
import sqlalchemy as sa

from flask import g, request
from http import HTTPStatus
from sqlalchemy import desc

from vantage6.common import logger_name
from vantage6.server import db
from vantage6.server.permission import (
    PermissionManager,
    Scope as S,
    Operation as P
)
from vantage6.server.resource import (
    with_node,
    only_for,
    parse_datetime,
    ServicesResources
)
from vantage6.server.resource.common.input_schema import RunInputSchema
from vantage6.server.resource.common.pagination import Pagination
from vantage6.server.resource.common._schema import (
    RunSchema, RunTaskIncludedSchema, ResultSchema
)
from vantage6.server.model import (
    Run as db_Run,
    Node,
    Task,
    Collaboration,
    Organization
)


module_name = logger_name(__name__)
log = logging.getLogger(module_name)


def setup(api, api_base, services):

    path = "/".join([api_base, module_name])
    log.info(f'Setting up "{path}" and subdirectories')

    api.add_resource(
        Runs,
        path,
        endpoint='run_without_id',
        methods=('GET',),
        resource_class_kwargs=services
    )
    api.add_resource(
        Run,
        path + '/<int:id>',
        endpoint='run_with_id',
        methods=('GET', 'PATCH'),
        resource_class_kwargs=services
    )
    api.add_resource(
        Results,
        api_base + '/result',
        endpoint='result_without_id',
        methods=('GET',),
        resource_class_kwargs=services
    )
    # TODO v4+ implement a PATCH method and use it to update the result. Then,
    # remove that from patching it in the Run resource.
    api.add_resource(
        Result,
        api_base + '/result/<int:id>',
        endpoint='result_with_id',
        methods=('GET',),
        resource_class_kwargs=services
    )


# Schemas
run_schema = RunSchema()
run_inc_schema = RunTaskIncludedSchema()
result_schema = ResultSchema()
run_input_schema = RunInputSchema()


# -----------------------------------------------------------------------------
# Permissions
# -----------------------------------------------------------------------------
def permissions(permissions: PermissionManager):
    add = permissions.appender(module_name)

    add(scope=S.GLOBAL, operation=P.VIEW,
        description="view any run")
    add(scope=S.ORGANIZATION, operation=P.VIEW, assign_to_container=True,
        assign_to_node=True, description="view runs of your organizations "
        "collaborations")


# ------------------------------------------------------------------------------
# Resources / API's
# ------------------------------------------------------------------------------
class RunBase(ServicesResources):

    def __init__(self, socketio, mail, api, permissions, config):
        super().__init__(socketio, mail, api, permissions, config)
        self.r = getattr(self.permissions, module_name)


class MultiRunBase(RunBase):
    """Base class for resources that return multiple runs or results"""

    def get_query_multiple_runs(self) -> Union[sa.orm.query.Query, tuple]:
        """
        Returns a query object that can be used to retrieve runs.

        Returns
        -------
        sa.orm.query.Query or tuple
            A query object to retrieve a single algorithm run, or a tuple with
            a message and HTTP error code if the query could not be set up
        """
        auth_org = self.obtain_auth_organization()
        args = request.args

        q = g.session.query(db_Run)

        # relation filters
        for param in ['task_id', 'organization_id', 'port']:
            if param in args:
                q = q.filter(getattr(db_Run, param) == args[param])

        # date selections
        for param in ['assigned', 'started', 'finished']:
            if f'{param}_till' in args:
                q = q.filter(getattr(db_Run, f'{param}_at')
                             <= args[f'{param}_till'])
            if f'{param}_from' in args:
                q = q.filter(db_Run.assigned_at >= args[f'{param}_from'])

        # custom filters
        if args.get('state') == 'open':
            q = q.filter(db_Run.finished_at == None)

        q = q.join(Organization).join(Node).join(Task, db_Run.task)\
            .join(Collaboration)

        if args.get('node_id'):
            q = q.filter(db.Node.id == args.get('node_id'))\
                .filter(db.Collaboration.id == db.Node.collaboration_id)

        # filter based on permissions
        if not self.r.v_glo.can():
            if self.r.v_org.can():
                col_ids = [col.id for col in auth_org.collaborations]
                q = q.filter(Collaboration.id.in_(col_ids))
            else:
                return {'msg': 'You lack the permission to do that!'}, \
                    HTTPStatus.UNAUTHORIZED

        # query the DB and paginate
        q = q.order_by(desc(db_Run.id))
        return q


class Runs(MultiRunBase):

    @only_for(['node', 'user', 'container'])
    def get(self):
        """ Returns a list of runs
        ---

        description: >-
            Returns a list of all runs you are allowed to see.\n

            ### Permission Table\n
            |Rule name|Scope|Operation|Assigned to node|Assigned to container|
            Description|\n
            |--|--|--|--|--|--|\n
            |Run|Global|View|❌|❌|View any run|\n
            |Run|Organization|View|✅|✅|View the runs of your
            organization's collaborations|\n

            Accessible to users.

        parameters:
            - in: query
              name: task_id
              schema:
                type: integer
              description: Task id
            - in: query
              name: organization_id
              schema:
                type: integer
              description: Organization id
            - in: query
              name: assigned_from
              schema:
                type: date (yyyy-mm-dd)
              description: Show only task assigned from this date
            - in: query
              name: started_from
              schema:
                type: date (yyyy-mm-dd)
              description: Show only task started from this date
            - in: query
              name: finished_from
              schema:
                type: date (yyyy-mm-dd)
              description: Show only task finished from this date
            - in: query
              name: assigned_till
              schema:
                type: date (yyyy-mm-dd)
              description: Show only task assigned till this date
            - in: query
              name: started_till
              schema:
                type: date (yyyy-mm-dd)
              description: Show only task started till this date
            - in: query
              name: finished_till
              schema:
                type: date (yyyy-mm-dd)
              description: Show only task finished till this date
            - in: query
              name: state
              schema:
                type: string
              description: The state of the task ('open')
            - in: query
              name: node_id
              schema:
                type: integer
              description: Node id
            - in: query
              name: port
              schema:
                type: integer
              description: Port number
            - in: query
              name: include
              schema:
                type: string (can be multiple)
              description: Include 'task' to include task data. Include
                'metadata' to get pagination metadata. Note that this will put
                the actual data in an envelope.
            - in: query
              name: page
              schema:
                type: integer
              description: Page number for pagination
            - in: query
              name: per_page
              schema:
                type: integer
              description: Number of items per page

        responses:
            200:
                description: Ok
            401:
                description: Unauthorized

        security:
        - bearerAuth: []

        tags: ["Algorithm"]
        """
        query = self.get_query_multiple_runs()

        # If no query is returned, we should return message and error code
        if not isinstance(query, sa.orm.query.Query):
            return query

        page = Pagination.from_query(query=query, request=request)

        # serialization of the models
        s = run_inc_schema if self.is_included('task') else run_schema

        return self.response(page, s)


class Results(MultiRunBase):

    @only_for(['node', 'user', 'container'])
    def get(self):
        """ Returns a list of results
        ---

        description: >-
            Returns a list of all results you are allowed to see.\n

            ### Permission Table\n
            |Rule name|Scope|Operation|Assigned to node|Assigned to container|
            Description|\n
            |--|--|--|--|--|--|\n
            |Run|Global|View|❌|❌|View any result|\n
            |Run|Organization|View|✅|✅|View the results of your
            organization's collaborations|\n

            Accessible to users.

        parameters:
            - in: query
              name: task_id
              schema:
                type: integer
              description: Task id
            - in: query
              name: organization_id
              schema:
                type: integer
              description: Organization id
            - in: query
              name: assigned_from
              schema:
                type: date (yyyy-mm-dd)
              description: Show only task assigned from this date
            - in: query
              name: started_from
              schema:
                type: date (yyyy-mm-dd)
              description: Show only task started from this date
            - in: query
              name: finished_from
              schema:
                type: date (yyyy-mm-dd)
              description: Show only task finished from this date
            - in: query
              name: assigned_till
              schema:
                type: date (yyyy-mm-dd)
              description: Show only task assigned till this date
            - in: query
              name: started_till
              schema:
                type: date (yyyy-mm-dd)
              description: Show only task started till this date
            - in: query
              name: finished_till
              schema:
                type: date (yyyy-mm-dd)
              description: Show only task finished till this date
            - in: query
              name: state
              schema:
                type: string
              description: The state of the task ('open')
            - in: query
              name: node_id
              schema:
                type: integer
              description: Node id
            - in: query
              name: port
              schema:
                type: integer
              description: Port number
            - in: query
              name: page
              schema:
                type: integer
              description: Page number for pagination
            - in: query
              name: per_page
              schema:
                type: integer
              description: Number of items per page
            - in: query
              name: sort
              schema:
                type: string
              description: >-
                Sort by one or more fields, separated by a comma. Use a minus
                sign (-) in front of the field to sort in descending order.

        responses:
            200:
                description: Ok
            401:
                description: Unauthorized

        security:
        - bearerAuth: []

        tags: ["Algorithm"]
        """
        query = self.get_query_multiple_runs()

        # If no query is returned, we should return message and error code
        if not isinstance(query, sa.orm.query.Query):
            return query

        page = Pagination.from_query(query=query, request=request)

        return self.response(page, result_schema)


class SingleRunBase(RunBase):
    """Base class for resources that return a single run or result"""

    def get_single_run(self, id) -> Union[db_Run, tuple]:
        """
        Set up a query to retrieve a single algorithm run

        Parameters
        ----------
        id : int
            The id of the run to retrieve

        Returns
        -------
        sa.orm.query.Query or tuple
            An algorithm Run object, or a tuple with a message and HTTP error
            code if the Run could not be retrieved
        """
        auth_org = self.obtain_auth_organization()

        run = db_Run.get(id)
        if not run:
            return {'msg': f'Run id={id} not found!'}, \
                HTTPStatus.NOT_FOUND
        if not self.r.v_glo.can():
            c_orgs = run.task.collaboration.organizations
            if not (self.r.v_org.can() and auth_org in c_orgs):
                return {'msg': 'You lack the permission to do that!'}, \
                    HTTPStatus.UNAUTHORIZED
        return run


class Run(SingleRunBase):
    """Resource for /api/run"""

    @only_for(['node', 'user', 'container'])
    def get(self, id):
        """ Get a single run's data
        ---

        description: >-
            Returns a run from a task specified by an id. \n

            ### Permission Table\n
            |Rule name|Scope|Operation|Assigned to node|Assigned to container|
            Description|\n
            |--|--|--|--|--|--|\n
            |Run|Global|View|❌|❌|View any run|\n
            |Run|Organization|View|✅|✅|View the runs of your
            organizations collaborations|\n

            Accessible to users.

        parameters:
          - in: path
            name: id
            schema:
              type: integer
            minimum: 1
            description: Task id
            required: true
          - in: query
            name: include
            schema:
              type: string
            description: what to include ('task')

        responses:
          200:
              description: Ok
          401:
              description: Unauthorized
          404:
              description: Run id not found

        security:
          - bearerAuth: []

        tags: ["Algorithm"]
        """
        run = self.get_single_run(id)

        # return error code if run is not found
        if not isinstance(run, db_Run):
            return run

        s = run_inc_schema if request.args.get('include') == 'task' \
            else run_schema

        return s.dump(run, many=False), HTTPStatus.OK

    @with_node
    def patch(self, id):
        """Update algorithm run data, for example to update the result
        ---
        description: >-
          Update runs from the node. Only done if the request comes from the
          correct, authenticated node.\n

          The user cannot access this endpoint so they cannot tamper with any
          runs.

        parameters:
          - in: path
            name: id
            schema:
              type: integer
              minimum: 1
            description: Task id
            required: tr

        requestBody:
          content:
            application/json:
              schema:
                properties:
                  started_at:
                    type: string
                    description: Time at which task was started
                  finished_at:
                    type: string
                    description: Time at which task was completed
                  result:
                    type: string
                    description: (Encrypted) result of the task
                  log:
                    type: string
                    description: Task log messages
                  status:
                    type: string
                    description: Status of the task

        responses:
          200:
            description: Ok
          400:
            description: Run already posted
          401:
            description: Unauthorized
          404:
            description: Run id not found

        security:
          - bearerAuth: []

        tags: ["Algorithm"]
        """
        run = db_Run.get(id)
        if not run:
            return {'msg': f'Run id={id} not found!'}, HTTPStatus.NOT_FOUND

        data = request.get_json()
        # validate request body
        errors = run_input_schema.validate(data, partial=True)
        if errors:
            return {'msg': 'Request body is incorrect', 'errors': errors}, \
                HTTPStatus.BAD_REQUEST

        if run.organization_id != g.node.organization_id:
            log.warn(
                f"{g.node.name} tries to update a run that does not belong "
                f"to them ({run.organization_id}/{g.node.organization_id})."
            )
            return {"msg": "This is not your algorithm run to PATCH!"}, \
                HTTPStatus.UNAUTHORIZED

        if run.finished_at is not None:
            return {
                "msg": "Cannot update an already finished algorithm run!"
            }, HTTPStatus.BAD_REQUEST

        # notify collaboration nodes/users that the task has an update
        self.socketio.emit(
            "status_update", {'run_id': id}, namespace='/tasks',
            room=f'collaboration_{run.task.collaboration.id}'
        )

        run.started_at = parse_datetime(data.get("started_at"),
                                        run.started_at)
        run.finished_at = parse_datetime(data.get("finished_at"))
        run.result = data.get("result")
        run.log = data.get("log")
        run.status = data.get("status", run.status)
        run.save()

        return run_schema.dump(run, many=False), HTTPStatus.OK


class Result(SingleRunBase):
    """Resource for /api/result/<id>"""

    @only_for(['node', 'user', 'container'])
    def get(self, id):
        """ Get a single result
        ---

        description: >-
            Returns a result specified by an algorithm run id. \n

            ### Permission Table\n
            |Rule name|Scope|Operation|Assigned to node|Assigned to container|
            Description|\n
            |--|--|--|--|--|--|\n
            |Run|Global|View|❌|❌|View any result|\n
            |Run|Organization|View|✅|✅|View the results of your
            organization's collaborations|\n

            Accessible to users.

        parameters:
          - in: path
            name: id
            schema:
              type: integer
            minimum: 1
            description: Algorithm run id
            required: true

        responses:
          200:
              description: Ok
          401:
              description: Unauthorized
          404:
              description: Run id not found

        security:
          - bearerAuth: []

        tags: ["Algorithm"]
        """
        run = self.get_single_run(id)

        # return error code if run is not found
        if not isinstance(run, db_Run):
            return run

        return result_schema.dump(run, many=False), HTTPStatus.OK
