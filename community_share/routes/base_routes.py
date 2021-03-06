import logging
from http import HTTPStatus
from functools import wraps

from flask import jsonify, request, Blueprint

from sqlalchemy.exc import IntegrityError, InvalidRequestError

from community_share import store
from community_share.app_exceptions import BadRequest, Unauthorized, Forbidden, NotFound
from community_share.utils import StatusCodes, is_integer
from community_share.authorization import get_requesting_user
from community_share.models.base import ValidationException


def make_not_authorized_response():
    response_data = {'message': 'Authorization failed'}
    response = jsonify(response_data)
    response.status_code = HTTPStatus.UNAUTHORIZED
    return response


def make_forbidden_response():
    response_data = {'message': 'Forbidden'}
    response = jsonify(response_data)
    response.status_code = StatusCodes.FORBIDDEN
    return response


def make_not_found_response():
    response_data = {'message': 'Not found'}
    response = jsonify(response_data)
    response.status_code = StatusCodes.NOT_FOUND
    return response


def make_bad_request_response(message=None):
    if message is None:
        message = 'Bad request'
    response_data = {'message': message}
    response = jsonify(response_data)
    response.status_code = HTTPStatus.BAD_REQUEST
    return response


def make_OK_response(message=None):
    if message is None:
        message = 'OK'
    response_data = {'message': message}
    response = jsonify(response_data)
    response.status_code = HTTPStatus.OK
    return response


def make_server_error_response(message=None):
    if message is None:
        message = 'Server error'
    response_data = {'message': message}
    response = jsonify(response_data)
    response.status_code = StatusCodes.SERVER_ERROR
    return response


def make_many_response(requester, items):
    serialized = [item.serialize(requester) for item in items]
    serialized = [s for s in serialized if s is not None]
    response_data = {'data': serialized}
    response = jsonify(response_data)
    return response


def make_single_response(requester, item, include_user=None):
    '''
    Sometimes we want to include the current user info in the response
    since it might be changed by a request.
    '''
    if item is None:
        raise NotFound()
    else:
        serialized = item.serialize(requester)
        if serialized is None:
            raise Forbidden()
        else:
            response_data = {'data': serialized}
            if include_user is not None:
                serialized_user = include_user.serialize(requester)
                response_data['user'] = serialized_user
            response = jsonify(response_data)
    return response


def make_blueprint(Item, resource_name):

    api = Blueprint(resource_name, __name__)

    @api.route(
        '/api/{0}'.format(resource_name),
        endpoint='get_many_{}'.format(resource_name),
        methods=['GET'],
    )
    def get_items():
        requester = get_requesting_user()
        if requester is None and not Item.PERMISSIONS.get('all_can_read_many', False):
            raise Unauthorized()
        else:
            if requester is None or not requester.is_administrator:
                if (Item.PERMISSIONS.get('standard_can_read_many', False) or
                    Item.PERMISSIONS.get('all_can_read_many', False)):
                    try:
                        query = Item.args_to_query(request.args, requester)
                        if query is None:
                            raise Forbidden()
                        else:
                            items = query.all()
                            response = make_many_response(requester, items)
                    except ValueError as e:
                        raise BadRequest(', '.join(e.args))
                else:
                    raise Forbidden()
            else:
                try:
                    query = Item.args_to_query(request.args, requester)
                    items = query.all()
                    response = make_many_response(requester, items)
                except ValueError as e:
                    raise BadRequest(', '.join(e.args))
        return response

    @api.route(
        '/api/{0}/<id>'.format(resource_name),
        endpoint='get_{}'.format(resource_name),
        methods=['GET'],
    )
    def get_item(id):
        requester = get_requesting_user()
        if requester is None:
            raise Unauthorized()
        elif not is_integer(id):
            raise BadRequest()
        else:
            item = store.session.query(Item).filter_by(id=id, active=True).first()
            if item is None:
                raise NotFound()
            else:
                response = make_single_response(requester, item)
        return response

    @api.route(
        '/api/{0}'.format(resource_name),
        endpoint='add_{}'.format(resource_name),
        methods=['POST'],
    )
    def add_item():
        requester = get_requesting_user()
        data = request.json
        if not Item.has_add_rights(data, requester):
            if requester is None:
                raise Unauthorized()
            else:
                raise Forbidden()
        else:
            try:
                item = Item.admin_deserialize_add(data)
                store.session.add(item)
                store.session.commit()
                refreshed_item = store.session.query(Item).filter_by(id=item.id).first()
                refreshed_item.on_add(requester)
                # commit again in case on_add changed it.
                store.session.commit()
                # and refresh again to update relationships
                refreshed_item = store.session.query(Item).filter_by(id=item.id).first()
                response = make_single_response(requester, refreshed_item, include_user=requester)
            except ValidationException as e:
                raise BadRequest(str(e))
            except (IntegrityError, InvalidRequestError) as e:
                if len(e.args) > 0:
                    message = e.args[0]
                else:
                    message = ''
                raise BadRequest(message)
        return response

    @api.route(
        '/api/{0}/<id>'.format(resource_name),
        endpoint='edit_{}'.format(resource_name),
        methods=['PATCH', 'PUT'],
    )
    def edit_item(id):
        requester = get_requesting_user()
        if requester is None:
            raise Unauthorized()
        elif not is_integer(id):
            raise BadRequest()
        else:
            id = int(id)
            data = request.json
            data_id = data.get('id', None)
            if data_id is not None and int(data_id) != id:
                raise BadRequest()
            else:
                if id is None:
                    item = None
                else:
                    item = store.session.query(Item).filter_by(id=id).first()
                if item is None:
                    raise NotFound()
                else:
                    if item.has_admin_rights(requester):
                        try:
                            item.admin_deserialize_update(data)
                            store.session.add(item)
                            item.on_edit(requester, unchanged=not store.session.dirty)
                            store.session.commit()
                            response = make_single_response(requester, item)
                        except ValidationException as e:
                            raise BadRequest(str(e))
                    else:
                        raise Forbidden()
        return response

    @api.route(
        '/api/{0}/<id>'.format(resource_name),
        endpoint='delete_{}'.format(resource_name),
        methods=['DELETE'],
    )
    def delete_item(id):
        requester = get_requesting_user()
        if requester is None:
            raise Unauthorized()
        elif not is_integer(id):
            raise BadRequest()
        else:
            id = int(id)
            item = store.session.query(Item).filter_by(id=id).first()
            if item is None:
                raise NotFound()
            else:
                if item.has_delete_rights(requester):
                    item.delete(requester)
                    store.session.commit()
                    response = make_single_response(requester, item)
                else:
                    raise Forbidden()
        return response

    return api
