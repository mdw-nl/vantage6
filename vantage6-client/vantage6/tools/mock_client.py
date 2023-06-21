import pandas as pd
import json

from importlib import import_module
from copy import deepcopy

from vantage6.tools.wrappers import select_wrapper
from vantage6.tools import serialization


class ClientMockProtocol:
    """
    The ClientMockProtocol is used to test your algorithm locally. It
    mimics the behaviour of the client and its communication with the server.

    Parameters
    ----------
    datasets : list[str]
        A list of paths to the datasets that are used in the algorithm.
    module : str
        The name of the module that contains the algorithm.
    """
    def __init__(self, datasets: list[str], module: str) -> None:
        self.n = len(datasets)
        self.datasets = []
        for dataset in datasets:
            self.datasets.append(
                pd.read_csv(dataset)
            )

        self.lib = import_module(module)
        self.tasks = []

    # TODO in v4+, don't provide a default value for list? There is no use
    # in calling this function with 0 organizations as the task will never
    # be executed in that case.
    def create_new_task(self, input_: dict,
                        organization_ids: list[int] = None) -> int:
        """
        Create a new task with the MockProtocol and return the task id.

        Parameters
        ----------
        input_ : dict
            The input data that is passed to the algorithm. This should at
            least  contain the key 'method' which is the name of the method
            that should be called. Another often used key is 'master' which
            indicates that this container is a master container. Other keys
            depend on the algorithm.
        organization_ids : list[int], optional
            A list of organization ids that should run the algorithm.

        Returns
        -------
        int
            The id of the task.
        """
        if organization_ids is None:
            organization_ids = []

        # extract method from lib and input
        master = input_.get("master")

        method_name = input_.get("method")
        if master:
            method = getattr(self.lib, method_name)
        else:
            method = getattr(self.lib, f"RPC_{method_name}")

        # get input
        args = input_.get("args", [])
        kwargs = input_.get("kwargs", {})

        # get data for organization
        results = []
        for org_id in organization_ids:
            data = self.datasets[org_id]
            if master:
                result = method(self, data, *args, **kwargs)
            else:
                result = method(data, *args, **kwargs)

            # TODO remove pickle in v4+
            idx = 999  # we dont need this now
            results.append(
                {"id": idx, "result": serialization.serialize(result)}
            )

        id_ = len(self.tasks)
        task = {
            "id": id_,
            "results": results,
            "complete": "true"
        }
        self.tasks.append(task)
        return task

    def get_task(self, task_id: int) -> dict:
        """
        Return the task with the given id.

        Parameters
        ----------
        task_id : int
            The id of the task.

        Returns
        -------
        dict
            The task details.
        """
        return self.tasks[task_id]

    def get_results(self, task_id: int) -> list[dict]:
        """
        Return the results of the task with the given id.

        Parameters
        ----------
        task_id : int
            The id of the task.

        Returns
        -------
        list[dict]
            The results of the task.
        """
        task = self.tasks[task_id]
        results = []
        for result in task.get("results"):
            res = json.loads(result.get("result"))
            results.append(res)

        return results

    def get_organizations_in_my_collaboration(self) -> list[dict]:
        """
        Get mocked organizations.

        Returns
        -------
        list[dict]
            A list of mocked organizations.
        """
        organizations = []
        for i in range(self.n):
            organizations.append({
                "id": i,
                "name": f"mock-{i}",
                "domain": f"mock-{i}.org",
            })
        return organizations


# TODO in v4+, rename to ClientMockProtocol?
class MockAlgorithmClient:
    """
    The MockAlgorithmClient mimics the behaviour of the AlgorithmClient. It
    can be used to mock the behaviour of the AlgorithmClient and its
    communication with the server.

    Parameters
    ----------
    datasets : list[dict]
        A list of dictionaries that contain the datasets that are used in the
        mocked algorithm. The dictionaries should contain the following:
        {
            "database": str | pd.DataFrame,
            "type": str,
            "input_data": dict
        }
        where database is the path/URI to the database, type is the database
        type (as listed in node configuration) and input_data contains
        the input data that is normally passed to the algorithm wrapper.

        Note that if the database is a pandas DataFrame, the type and
        input_data keys are not required.
    module : str
        The name of the module that contains the algorithm.
    node_id : int, optional
        Sets the mocked node id that to this value. Defaults to 1.
    collaboration_id : int, optional
        Sets the mocked collaboration id to this value. Defaults to 1.
    organization_id : int, optional
        Sets the mocked organization id to this value. Defaults to 1.
    """
    # TODO not only read CSVs but also data types
    def __init__(
        self, datasets: list[dict], module: str, node_id: int = None,
        collaboration_id: int = None, organization_id: int = None
    ) -> None:
        self.n = len(datasets)
        self.datasets = []
        for dataset in datasets:
            if isinstance(dataset["database"], pd.DataFrame):
                self.datasets.append(dataset["database"])
            else:
                wrapper = select_wrapper(dataset["type"])
                self.datasets.append(
                    wrapper.load_data(
                        dataset["database"],
                        dataset["input_data"] if "input_data" in dataset
                        else {}
                    )
                )

        self.lib = import_module(module)
        self.tasks = []

        self.image = 'mock_image'
        self.database = 'mock_database'
        self.host_node_id = node_id if node_id else 1
        self.collaboration_id = collaboration_id if collaboration_id else 1
        self.organization_id = organization_id if organization_id else 1

        self.task = self.Task(self)
        self.result = self.Result(self)
        self.organization = self.Organization(self)
        self.collaboration = self.Collaboration(self)
        self.node = self.Node(self)

    class SubClient:
        """
        Create sub groups of commands using this SubClient

        Parameters
        ----------
        parent : MockAlgorithmClient
            The parent client
        """
        def __init__(self, parent) -> None:
            self.parent: MockAlgorithmClient = parent

    class Task(SubClient):
        """
        Task subclient for the MockAlgorithmClient
        """
        def create(
            self, input_: dict, organization_ids: list[int],
            name: str = "mock", description: str = "mock", *args, **kwargs
        ) -> int:
            """
            Create a new task with the MockProtocol and return the task id.

            Parameters
            ----------
            input_ : dict
                The input data that is passed to the algorithm. This should at
                least  contain the key 'method' which is the name of the method
                that should be called. Another often used key is 'master' which
                indicates that this container is a master container. Other keys
                depend on the algorithm.
            organization_ids : list[int]
                A list of organization ids that should run the algorithm.
            name : str, optional
                The name of the task, by default "mock"
            description : str, optional
                The description of the task, by default "mock"

            Returns
            -------
            int
                The id of the task.
            """
            if not len(organization_ids):
                raise ValueError(
                    "No organization ids provided. Cannot create a task for "
                    "zero organizations."
                )

            # extract method from lib and input
            # TODO in v4+, there is no master and this should be removed
            master = input_.get("master")

            method_name = input_.get("method")
            if master:
                method = getattr(self.parent.lib, method_name)
            else:
                method = getattr(self.parent.lib, f"RPC_{method_name}")

            # get input
            args = input_.get("args", [])
            kwargs = input_.get("kwargs", {})

            # get data for organization
            results = []
            for org_id in organization_ids:
                data = self.parent.datasets[org_id]
                if master:
                    # ensure that a task has a node_id and organization id that
                    # is unique compared to other tasks.
                    client_copy = deepcopy(self.parent)
                    client_copy.host_node_id = org_id
                    client_copy.organization_id = org_id
                    result = method(self.parent, data, *args, **kwargs)
                else:
                    result = method(data, *args, **kwargs)

                idx = 999  # we dont need this now
                results.append(
                    {"id": idx, "result": json.dumps(result)}
                )

            id_ = len(self.parent.tasks)
            collab_id = self.parent.collaboration_id
            # TODO adapt fields in v4+
            task = {
                "id": id_,
                "results": results,
                "complete": "true",  # TODO remove in v4+.
                "status": "completed",
                "name": name,
                "database": "mock",
                "description": description,
                "image": "mock_image",
                "init_user": {
                    "id": 1,
                    "link": "/api/user/1",
                    "methods": [
                        "DELETE",
                        "PATCH",
                        "GET"
                    ]
                },
                "init_org": {
                    "id": 1,
                    "link": "/api/organization/1",
                    "methods": [
                        "PATCH",
                        "GET"
                    ]
                },
                "parent": None,
                "collaboration": {
                    "id": collab_id,
                    "link": f"/api/collaboration/{collab_id}",
                    "methods": [
                        "DELETE",
                        "PATCH",
                        "GET"
                    ]
                },
                "run_id": 1,
                "children": None,
            }
            self.parent.tasks.append(task)
            return task

        def get(self, task_id: int) -> dict:
            """
            Return the task with the given id.

            Parameters
            ----------
            task_id : int
                The id of the task.

            Returns
            -------
            dict
                The task details.
            """
            return self.parent.tasks[task_id]

    # TODO for v4+, add a Run class
    class Result(SubClient):
        """
        Result subclient for the MockAlgorithmClient
        """
        def get(self, task_id: int) -> list[dict]:
            """
            Return the results of the task with the given id.

            Parameters
            ----------
            task_id : int
                The id of the task.

            Returns
            -------
            list[dict]
                The results of the task.
            """
            task = self.parent.tasks[task_id]
            results = []
            for result in task.get("results"):
                # TODO in v4+, this is no longer a pickle
                res = json.loads(result.get("result"))
                results.append(res)

            return results

    class Organization(SubClient):
        """
        Organization subclient for the MockAlgorithmClient
        """
        def get(self, id_) -> dict:
            """
            Get mocked organization by ID

            Parameters
            ----------
            id_ : int
                The id of the organization.

            Returns
            -------
            dict
                A mocked organization.
            """
            return {
                "id": id_,
                "name": f"mock-{id_}",
                "domain": f"mock-{id_}.org",
                "address1": "mock",
                "address2": "mock",
                "zipcode": "mock",
                "country": "mock",
                "public_key": "mock",
                "collaborations": f"/api/collaboration?organization_id={id_}",
                "users": f"/api/user?organization_id={id_}",
                "tasks": f"/api/task?init_org_id={id_}",
                "nodes": f"/api/node?organization_id={id_}",
                "runs": f"/api/run?organization_id={id_}"
            }

        def list(self) -> list[dict]:
            """
            Get mocked organizations in the collaboration.

            Returns
            -------
            list[dict]
                A list of mocked organizations in the collaboration.
            """
            organizations = []
            for i in range(self.parent.n):
                organizations.append(self.get(i))
            return organizations

    class Collaboration(SubClient):
        """
        Collaboration subclient for the MockAlgorithmClient
        """
        def get(self, is_encrypted: bool = True) -> dict:
            """
            Get mocked collaboration

            Parameters
            ----------
            is_encrypted : bool
                Whether the collaboration is encrypted or not. Default True.

            Returns
            -------
            dict
                A mocked collaboration.
            """
            collab_id = self.parent.collaboration_id
            return {
                "id": collab_id,
                "name": "mock-collaboration",
                "encrypted": is_encrypted,
                "tasks": f"/api/task?collaboration_id={collab_id}",
                "nodes": f"/api/node?collaboration_id={collab_id}",
                "organizations":
                    f"/api/organization?collaboration_id={collab_id}"
            }

    class Node(SubClient):
        """
        Node subclient for the MockAlgorithmClient
        """
        def get(self, is_online: bool = True) -> dict:
            """
            Get mocked node

            Parameters
            ----------
            is_online : bool
                Whether the node is online or not. Default True.

            Returns
            -------
            dict
                A mocked node.
            """
            node_id = self.parent.host_node_id
            collab_id = self.parent.collaboration_id
            return {
                "id": node_id,
                "name": "mock-node",
                "status": "online" if is_online else "offline",
                "ip": "1.2.3.4",
                "config": {
                    "key": "value",
                },
                "collaboration": {
                    "id": collab_id,
                    "link": f"/api/collaboration/{collab_id}",
                    "methods": [
                        "DELETE",
                        "PATCH",
                        "GET"
                    ]
                },
                "last_seen": "2021-01-01T00:00:00.000000",
                "type": "node",
                "organization": {
                    "id": node_id,
                    "link": f"/api/organization/{node_id}",
                    "methods": [
                        "GET",
                        "PATCH"
                    ]
                },
            }

    # TODO implement the get_addresses method before using this part
    # class VPN(SubClient):
    #     """
    #     VPN subclient for the MockAlgorithmClient
    #     """
    #     def get_addresses(
    #         self, only_children: bool = False, only_parent: bool = False,
    #         include_children: bool = False, include_parent: bool = False,
    #         label: str = None
    #     ) -> list[dict] | dict:
    #         """
    #         Mock VPN IP addresses and ports of other algorithm containers in
    #         the current task.

    #         Parameters
    #         ----------
    #         only_children : bool, optional
    #             Only return the IP addresses of the children of the current
    #             task, by default False. Incompatible with only_parent.
    #         only_parent : bool, optional
    #             Only return the IP address of the parent of the current task,
    #             by default False. Incompatible with only_children.
    #         include_children : bool, optional
    #             Include the IP addresses of the children of the current task,
    #             by default False. Incompatible with only_parent, superseded
    #             by only_children.
    #         include_parent : bool, optional
    #             Include the IP address of the parent of the current task, by
    #             default False. Incompatible with only_children, superseded by
    #             only_parent.
    #         label : str, optional
    #             The label of the port you are interested in, which is set
    #             in the algorithm Dockerfile. If this parameter is set, only
    #             the ports with this label will be returned.

    #         Returns
    #         -------
    #         list[dict] | dict
    #             List of dictionaries containing the IP address and port number,
    #             and other information to identify the containers. If obtaining
    #             the VPN addresses from the server fails, a dictionary with a
    #             'message' key is returned instead.
    #         """
    #         pass

    #     def get_parent_address(self) -> dict:
    #         """
    #         Get the IP address and port number of the parent of the current
    #         task.

    #         Returns
    #         -------
    #         dict
    #             Dictionary containing the IP address and port number, and other
    #             information to identify the containers. If obtaining the VPN
    #             addresses from the server fails, a dictionary with a 'message'
    #             key is returned instead.
    #         """
    #         return self.get_addresses(only_parent=True)

    #     def get_child_addresses(self) -> list[dict]:
    #         """
    #         Get the IP addresses and port numbers of the children of the
    #         current task.

    #         Returns
    #         -------
    #         List[dict]
    #             List of dictionaries containing the IP address and port number,
    #             and other information to identify the containers. If obtaining
    #             the VPN addresses from the server fails, a dictionary with a
    #             'message' key is returned instead.
    #         """
    #         return self.get_addresses(only_children=True)
