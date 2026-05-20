

.. _blob-storage:

Blob Storage
------------

The large result store has two backends, selected via the ``type`` field of
the ``large_result_store`` configuration block:

- ``azure`` — Azure Blob Storage (see below).
- ``file`` — local filesystem (see :ref:`file-storage-backend`).

If ``type`` is omitted, ``file`` is assumed.
If ``type`` is unrecognised, the large result store is disabled and a
warning is logged at startup.

Azure backend
+++++++++++++

To use Azure Blob Storage, the following can be set in the server
configuration file:

::
    
  large_result_store:
    type: "azure"
    container_name: test-container
    tenant_id: "your-tenant-id"
    client_id: "your-client-id"
    client_secret: "your-client-secret"
    storage_account_name: "your-storage-account-name"

The 'test-container' refers to the azure blob container
(unrelated to Docker containers) in which all blobs are stored. This container should be created in advance manually.
Tenant id, client id and client secret are required for authentication (For help on setting up a managed identity,
see `here <https://learn.microsoft.com/en-us/azure/storage/blobs/authorize-access-azure-active-directory>`__).

For development and testing purposes, `Azurite 
<https://github.com/Azure/Azurite>`__ can be used. There are subtle differences
between the two, so be aware that it will not be completely representative of
the production environment.


To use Azurite, a connection string can be configured instead. In the example below,
the Azurite default connection string is used, with the endpoints adjusted to
point to a local Azurite instance. 

::
    
  large_result_store:
    type: "azure"
    container_name: test-container
    connection_string: "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://172.17.0.1:10000/devstoreaccount1;QueueEndpoint=http://172.17.0.1:10001/devstoreaccount1;"

.. warning::
    Note that while it is also possible to use a connection string to connect to Azure Blob Storage,
    it is not recommended (accountname and accountkey will be stored plainly in the configuration,
    no automatic rotation, no fine-grained permissions via RBAC and so on).

.. _file-storage-backend:

File backend
++++++++++++

To store blobs on the local filesystem instead of Azure, set ``type`` to
``file``:

::

  large_result_store:
    type: "file"
    # base_path: "/var/lib/vantage6/blobs"   # optional, see below
    # container_name: "results"              # optional subdirectory

When the server is started via ``v6 server start`` the CLI automatically
bind-mounts the host directory into the container at ``/mnt/blobs`` and
pins the in-container path with the ``VANTAGE6_BLOB_BASE_PATH``
environment variable. The mount is created from ``base_path`` if set,
otherwise from ``<server data dir>/blobs`` (next to where the server
already keeps its logs and SQLite database). This makes it physically
impossible for the in-container default to be picked up, so beginners
get persistence on the host without having to configure any volume
mounts. The CLI prints the resolved host path at startup.

Blobs are written under a two-character shard derived from the UUID
identifier (``{base_path}/{uuid[:2]}/{uuid}``) to keep individual
directories from growing without bound. Writes are atomic: a tempfile
is ``fsync``-ed and then renamed into place, so readers never observe
a half-written blob.

.. warning::
    For multi-replica deployments ``base_path`` must point at a shared
    filesystem (NFS, Azure Files, …). Replicas using local-only storage
    will not see each other's blobs.

Developer documentation
+++++++++++++++++++++++

When configured to use blob storage, inputs and results are streamed:

- From the user client, through the server, to blob storage and vice versa
- From the node client, through the server, to blob storage and vice versa
- From the algorithm container, through the proxy, server to blob storage and vice versa

Whenever a blob is uploaded, it is stored using a UUID as identifier. This UUID is then used
as reference in the `input` or `result` field in the database. To ensure backwards compatibility,
checks are made throughout the code to determine if the run was performed using the relational 
database, in which case the input or result should be interpreted as is, as opposed to first retrieving
the data from blob storage.

The `blobstream` endpoint on the server enables streaming of large input and result data 
directly to and from blob storage. This reduces memory usage by never storing the entire input 
or result in memory at once, and avoids storing large payloads in the database.

Encryption
~~~~~~~~~~

Since inputs and results are now uploaded and downloaded separately and are no longer part of 
a larger JSON object, Base64 encoding is skipped when data is encrypted. The encrypted raw bytes 
can be stored directly.
Inputs are encrypted before uploading, and results are decrypted after downloading in the node and client.
Since encryption and decryption for the algorithm container takes place in the proxy, for the algorithm
encryption and decryption is done on a chunk by chunk basis using **AES-CTR** to prevent loading the entire
input or result into memory at once.

Database
~~~~~~~~

A blob_storage column is added to the `runs` table to indicate whether blob storage and streaming was used for that run.
This ensures for any run it is clear whether the input or result field should be interpreted directly, or first 
retrieved. For existing installations, empty values for `blob_storage_used` are assumed to be False.