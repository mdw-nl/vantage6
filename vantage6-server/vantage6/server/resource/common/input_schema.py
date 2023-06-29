import uuid
import ipaddress

from marshmallow import (
    Schema, fields, ValidationError, validates, validates_schema
)
from marshmallow.validate import Length, Range, OneOf

from vantage6.common.task_status import TaskStatus


class _OnlyIdSchema(Schema):
    """ Schema for validating POST requests that only require an ID field. """
    id = fields.Integer(required=True, validate=Range(min=1))


class ChangePasswordInputSchema(Schema):
    """ Schema for validating input for changing a password. """
    current_password = fields.String(required=True, validate=Length(max=128))
    new_password = fields.String(required=True, validate=Length(max=128))


class CollaborationInputSchema(Schema):
    """ Schema for validating input for a creating a collaboration. """
    name = fields.String(required=True, validate=Length(max=128))
    organization_ids = fields.List(fields.Integer(), required=True)
    encrypted = fields.Boolean(required=True)

    @validates('organization_ids')
    def validate_organization_ids(self, organization_ids):
        """
        Validate the organization ids in the input.

        Parameters
        ----------
        organization_ids : list[int]
            List of organization ids to validate.

        Raises
        ------
        ValidationError
            If the organization ids are not valid.
        """
        if not all(i > 0 for i in organization_ids):
            raise ValidationError('Organization ids must be greater than 0')
        if not len(organization_ids) == len(set(organization_ids)):
            raise ValidationError('Organization ids must be unique')
        if not len(organization_ids):
            raise ValidationError('At least one organization id is required')


class CollaborationAddOrganizationSchema(_OnlyIdSchema):
    """
    Schema for validating requests that add an organization to a collaboration.
    """
    pass


class CollaborationAddNodeSchema(_OnlyIdSchema):
    """ Schema for validating requests that add a node to a collaboration. """
    pass


class KillTaskInputSchema(_OnlyIdSchema):
    """ Schema for validating input for killing a task. """
    pass


class KillNodeTasksInputSchema(_OnlyIdSchema):
    """ Schema for validating input for killing tasks on a node. """
    pass


class NodeInputSchema(Schema):
    """ Schema for validating input for a creating a node. """
    name = fields.String(validate=Length(max=128))
    collaboration_id = fields.Integer(required=True, validate=Range(min=1))
    organization_id = fields.Integer(validate=Range(min=1))
    ip = fields.String()
    clear_ip = fields.Boolean()

    @validates('ip')
    def validate_ip(self, ip: str):
        """
        Validate IP address in request body.

        Parameters
        ----------
        ip : str
            IP address to validate.

        Raises
        ------
        ValidationError
            If the IP address is not valid.
        """
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            raise ValidationError('IP address is not valid')


class OrganizationInputSchema(Schema):
    """ Schema for validating input for a creating an organization. """
    name = fields.String(required=True, validate=Length(max=128))
    address1 = fields.String(validate=Length(max=128))
    address2 = fields.String(validate=Length(max=128))
    zipcode = fields.String(validate=Length(max=128))
    country = fields.String(validate=Length(max=128))
    domain = fields.String(validate=Length(max=128))
    public_key = fields.String()


class PortInputSchema(Schema):
    """ Schema for validating input for a creating a port. """
    port = fields.Integer(required=True)
    run_id = fields.Integer(required=True, validate=Range(min=1))
    label = fields.String(validate=Length(max=128))

    @validates('port')
    def validate_port(self, port):
        """
        Validate the port in the input.

        Parameters
        ----------
        port : int
            Port to validate.

        Raises
        ------
        ValidationError
            If the port is not valid.
        """
        if not 1 <= port <= 65535:
            raise ValidationError('Port must be between 1 and 65535')


class RecoverPasswordInputSchema(Schema):
    """ Schema for validating input for recovering a password. """
    email = fields.Email(validate=Length(max=256))
    username = fields.String(validate=Length(max=128))

    @validates_schema
    def validate_email_or_username(self, data, **kwargs):
        if not ('email' in data or 'username' in data):
            raise ValidationError('Email or username is required')


class ResetPasswordInputSchema(Schema):
    """ Schema for validating input for resetting a password. """
    reset_token = fields.String(required=True, validate=Length(max=512))
    password = fields.String(required=True, validate=Length(max=128))


class Recover2FAInputSchema(Schema):
    """ Schema for validating input for recovering 2FA. """
    email = fields.Email(validate=Length(max=256))
    username = fields.String(validate=Length(max=128))
    password = fields.String(validate=Length(max=128))

    @validates_schema
    def validate_email_or_username(self, data: dict, **kwargs):
        """
        Validate the input, which should contain either an email or username.

        Parameters
        ----------
        data : dict
            The input data.

        Raises
        ------
        ValidationError
            If the input does not contain an email or username.
        """
        if not ('email' in data or 'username' in data):
            raise ValidationError('Email or username is required')


class Reset2FAInputSchema(Schema):
    """ Schema for validating input for resetting 2FA. """
    reset_token = fields.String(required=True, validate=Length(max=512))


class ResetAPIKeyInputSchema(_OnlyIdSchema):
    """ Schema for validating input for resetting an API key. """
    pass


class RoleInputSchema(Schema):
    """ Schema for validating input for creating a role. """
    # TODO add check that name cannot be one of default roles
    name = fields.String(required=True, validate=Length(max=128))
    description = fields.String(validate=Length(max=512))
    rules = fields.List(fields.Integer(validate=Range(min=1)), required=True)
    organization_id = fields.Integer(validate=Range(min=1))


class RunInputSchema(Schema):
    """ Schema for validating input for patching an algorithm run. """
    started_at = fields.DateTime()
    finished_at = fields.DateTime()
    log = fields.String()
    result = fields.String()
    status = fields.String(validate=OneOf([s.value for s in TaskStatus]))


class TaskInputSchema(Schema):
    """ Schema for validating input for creating a task. """
    name = fields.String(validate=Length(max=128))
    description = fields.String(validate=Length(max=512))
    image = fields.String(required=True)
    collaboration_id = fields.Integer(required=True, validate=Range(min=1))
    organizations = fields.List(fields.Dict(), required=True)
    databases = fields.List(fields.String())

    @validates('organizations')
    def validate_organizations(self, organizations: list[dict]):
        """
        Validate the organizations in the input.

        Parameters
        ----------
        organizations : list[dict]
            List of organizations to validate. Each organization must have an
            id and input.

        Raises
        ------
        ValidationError
            If the organizations are not valid.
        """
        if not len(organizations):
            raise ValidationError('At least one organization is required')
        for organization in organizations:
            if 'id' not in organization:
                raise ValidationError(
                    'Organization id is required for each organization')
            if 'input' not in organization:
                raise ValidationError(
                    'Input is required for each organization')


class TokenUserInputSchema(Schema):
    """ Schema for validating input for creating a token for a user. """
    username = fields.String(required=True, validate=Length(max=128))
    password = fields.String(required=True, validate=Length(max=128))
    mfa_code = fields.String(validate=Length(equal=6))


class TokenNodeInputSchema(Schema):
    """ Schema for validating input for creating a token for a node. """
    api_key = fields.String(required=True)

    @validates('api_key')
    def validate_api_key(self, api_key: str):
        """
        Validate the API key in the input. The API key should be a valid UUID

        Parameters
        ----------
        api_key : str
            API key to validate.

        Raises
        ------
        ValidationError
            If the API key is not valid.
        """
        try:
            uuid.UUID(api_key)
        except ValueError:
            raise ValidationError('API key is not a valid UUID')


class TokenAlgorithmInputSchema(Schema):
    """ Schema for validating input for creating a token for an algorithm. """
    task_id = fields.Integer(required=True, validate=Range(min=1))
    image = fields.String(required=True)


class UserInputSchema(Schema):
    """ Schema for validating input for creating a user. """
    username = fields.String(required=True, validate=Length(max=128))
    email = fields.Email(required=True, validate=Length(max=256))
    # TODO use the checks from user.set_password() to validate proper password
    # also in other places in this file
    password = fields.String(required=True, validate=Length(max=128))
    firstname = fields.String(validate=Length(max=128))
    lastname = fields.String(validate=Length(max=128))
    organization_id = fields.Integer(validate=Range(min=1))
    roles = fields.List(fields.Integer(validate=Range(min=1)))
    rules = fields.List(fields.Integer(validate=Range(min=1)))


class VPNConfigUpdateInputSchema(Schema):
    """ Schema for validating input for updating a VPN configuration. """
    vpn_config = fields.String(required=True)
