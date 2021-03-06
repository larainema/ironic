# Copyright 2013 Red Hat, Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import datetime

import pecan
from pecan import rest
import wsme
from wsme import types as wtypes

from ironic.api.controllers import base
from ironic.api.controllers import link
from ironic.api.controllers.v1 import collection
from ironic.api.controllers.v1 import node
from ironic.api.controllers.v1 import types
from ironic.api.controllers.v1 import utils as api_utils
from ironic.api import expose
from ironic.common import exception
from ironic.common.i18n import _
from ironic import objects


_DEFAULT_RETURN_FIELDS = ('uuid', 'description')


class ChassisPatchType(types.JsonPatchType):
    pass


class Chassis(base.APIBase):
    """API representation of a chassis.

    This class enforces type checking and value constraints, and converts
    between the internal object model and the API representation of
    a chassis.
    """

    uuid = types.uuid
    """The UUID of the chassis"""

    description = wtypes.text
    """The description of the chassis"""

    extra = {wtypes.text: types.jsontype}
    """The metadata of the chassis"""

    links = wsme.wsattr([link.Link], readonly=True)
    """A list containing a self link and associated chassis links"""

    nodes = wsme.wsattr([link.Link], readonly=True)
    """Links to the collection of nodes contained in this chassis"""

    def __init__(self, **kwargs):
        self.fields = []
        for field in objects.Chassis.fields:
            # Skip fields we do not expose.
            if not hasattr(self, field):
                continue
            self.fields.append(field)
            setattr(self, field, kwargs.get(field, wtypes.Unset))

    @staticmethod
    def _convert_with_links(chassis, url, fields=None):
        # NOTE(lucasagomes): Since we are able to return a specified set of
        # fields the "uuid" can be unset, so we need to save it in another
        # variable to use when building the links
        chassis_uuid = chassis.uuid
        if fields is not None:
            chassis.unset_fields_except(fields)
        else:
            chassis.nodes = [link.Link.make_link('self',
                                                 url,
                                                 'chassis',
                                                 chassis_uuid + "/nodes"),
                             link.Link.make_link('bookmark',
                                                 url,
                                                 'chassis',
                                                 chassis_uuid + "/nodes",
                                                 bookmark=True)
                             ]
        chassis.links = [link.Link.make_link('self',
                                             url,
                                             'chassis', chassis_uuid),
                         link.Link.make_link('bookmark',
                                             url,
                                             'chassis', chassis_uuid,
                                             bookmark=True)
                         ]
        return chassis

    @classmethod
    def convert_with_links(cls, rpc_chassis, fields=None):
        chassis = Chassis(**rpc_chassis.as_dict())

        if fields is not None:
            api_utils.check_for_invalid_fields(fields, chassis.as_dict())

        return cls._convert_with_links(chassis, pecan.request.host_url,
                                       fields)

    @classmethod
    def sample(cls, expand=True):
        time = datetime.datetime(2000, 1, 1, 12, 0, 0)
        sample = cls(uuid='eaaca217-e7d8-47b4-bb41-3f99f20eed89', extra={},
                     description='Sample chassis', created_at=time,
                     updated_at=time)
        fields = None if expand else _DEFAULT_RETURN_FIELDS
        return cls._convert_with_links(sample, 'http://localhost:6385',
                                       fields=fields)


class ChassisCollection(collection.Collection):
    """API representation of a collection of chassis."""

    chassis = [Chassis]
    """A list containing chassis objects"""

    def __init__(self, **kwargs):
        self._type = 'chassis'

    @staticmethod
    def convert_with_links(chassis, limit, url=None, fields=None, **kwargs):
        collection = ChassisCollection()
        collection.chassis = [Chassis.convert_with_links(ch, fields=fields)
                              for ch in chassis]
        url = url or None
        collection.next = collection.get_next(limit, url=url, **kwargs)
        return collection

    @classmethod
    def sample(cls):
        sample = cls()
        sample.chassis = [Chassis.sample(expand=False)]
        return sample


class ChassisController(rest.RestController):
    """REST controller for Chassis."""

    nodes = node.NodesController()
    """Expose nodes as a sub-element of chassis"""

    # Set the flag to indicate that the requests to this resource are
    # coming from a top-level resource
    nodes.from_chassis = True

    _custom_actions = {
        'detail': ['GET'],
    }

    invalid_sort_key_list = ['extra']

    def _get_chassis_collection(self, marker, limit, sort_key, sort_dir,
                                resource_url=None, fields=None):
        limit = api_utils.validate_limit(limit)
        sort_dir = api_utils.validate_sort_dir(sort_dir)
        marker_obj = None
        if marker:
            marker_obj = objects.Chassis.get_by_uuid(pecan.request.context,
                                                     marker)

        if sort_key in self.invalid_sort_key_list:
            raise exception.InvalidParameterValue(
                _("The sort_key value %(key)s is an invalid field for sorting")
                % {'key': sort_key})

        chassis = objects.Chassis.list(pecan.request.context, limit,
                                       marker_obj, sort_key=sort_key,
                                       sort_dir=sort_dir)
        return ChassisCollection.convert_with_links(chassis, limit,
                                                    url=resource_url,
                                                    fields=fields,
                                                    sort_key=sort_key,
                                                    sort_dir=sort_dir)

    @expose.expose(ChassisCollection, types.uuid, int,
                   wtypes.text, wtypes.text, types.listtype)
    def get_all(self, marker=None, limit=None, sort_key='id', sort_dir='asc',
                fields=None):
        """Retrieve a list of chassis.

        :param marker: pagination marker for large data sets.
        :param limit: maximum number of resources to return in a single result.
        :param sort_key: column to sort results by. Default: id.
        :param sort_dir: direction to sort. "asc" or "desc". Default: asc.
        :param fields: Optional, a list with a specified set of fields
            of the resource to be returned.
        """
        api_utils.check_allow_specify_fields(fields)
        if fields is None:
            fields = _DEFAULT_RETURN_FIELDS
        return self._get_chassis_collection(marker, limit, sort_key, sort_dir,
                                            fields=fields)

    @expose.expose(ChassisCollection, types.uuid, int,
                   wtypes.text, wtypes.text)
    def detail(self, marker=None, limit=None, sort_key='id', sort_dir='asc'):
        """Retrieve a list of chassis with detail.

        :param marker: pagination marker for large data sets.
        :param limit: maximum number of resources to return in a single result.
        :param sort_key: column to sort results by. Default: id.
        :param sort_dir: direction to sort. "asc" or "desc". Default: asc.
        """
        # /detail should only work against collections
        parent = pecan.request.path.split('/')[:-1][-1]
        if parent != "chassis":
            raise exception.HTTPNotFound

        resource_url = '/'.join(['chassis', 'detail'])
        return self._get_chassis_collection(marker, limit, sort_key, sort_dir,
                                            resource_url)

    @expose.expose(Chassis, types.uuid, types.listtype)
    def get_one(self, chassis_uuid, fields=None):
        """Retrieve information about the given chassis.

        :param chassis_uuid: UUID of a chassis.
        :param fields: Optional, a list with a specified set of fields
            of the resource to be returned.
        """
        api_utils.check_allow_specify_fields(fields)
        rpc_chassis = objects.Chassis.get_by_uuid(pecan.request.context,
                                                  chassis_uuid)
        return Chassis.convert_with_links(rpc_chassis, fields=fields)

    @expose.expose(Chassis, body=Chassis, status_code=201)
    def post(self, chassis):
        """Create a new chassis.

        :param chassis: a chassis within the request body.
        """
        new_chassis = objects.Chassis(pecan.request.context,
                                      **chassis.as_dict())
        new_chassis.create()
        # Set the HTTP Location Header
        pecan.response.location = link.build_url('chassis', new_chassis.uuid)
        return Chassis.convert_with_links(new_chassis)

    @wsme.validate(types.uuid, [ChassisPatchType])
    @expose.expose(Chassis, types.uuid, body=[ChassisPatchType])
    def patch(self, chassis_uuid, patch):
        """Update an existing chassis.

        :param chassis_uuid: UUID of a chassis.
        :param patch: a json PATCH document to apply to this chassis.
        """
        rpc_chassis = objects.Chassis.get_by_uuid(pecan.request.context,
                                                  chassis_uuid)
        try:
            chassis = Chassis(
                **api_utils.apply_jsonpatch(rpc_chassis.as_dict(), patch))

        except api_utils.JSONPATCH_EXCEPTIONS as e:
            raise exception.PatchError(patch=patch, reason=e)

        # Update only the fields that have changed
        for field in objects.Chassis.fields:
            try:
                patch_val = getattr(chassis, field)
            except AttributeError:
                # Ignore fields that aren't exposed in the API
                continue
            if patch_val == wtypes.Unset:
                patch_val = None
            if rpc_chassis[field] != patch_val:
                rpc_chassis[field] = patch_val

        rpc_chassis.save()
        return Chassis.convert_with_links(rpc_chassis)

    @expose.expose(None, types.uuid, status_code=204)
    def delete(self, chassis_uuid):
        """Delete a chassis.

        :param chassis_uuid: UUID of a chassis.
        """
        rpc_chassis = objects.Chassis.get_by_uuid(pecan.request.context,
                                                  chassis_uuid)
        rpc_chassis.destroy()
