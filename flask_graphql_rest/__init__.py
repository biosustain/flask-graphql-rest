from flask.testing import FlaskClient
from typing import Optional

import flask
import graphene
import graphql.language.ast as graphql_ast
import pytest
from flask import Flask, Response, json
from graphene.test import format_execution_result, default_format_error
from graphql import GraphQLScalarType, GraphQLEnumType, GraphQLObjectType
from graphql_server import encode_execution_results, json_encode


class GraphQLREST(object):
    schema: graphene.Schema
    app: flask.Flask = None

    def __init__(self, schema: graphene.Schema, app: flask.Flask = None):
        self.schema = schema

        if app is not None:
            self.init_app(app)

    def init_app(self, app: flask.Flask):
        self.app = app

        query_type = self.schema.get_query_type()

        print(query_type, query_type.fields)
        for field_name, field in query_type.fields.items():
            endpoint = f'mutation.{query_type.name}.{field_name}'

            app.add_url_rule(f'/{field_name}',
                             view_func=self._get_query_view_func(field, field_name),
                             endpoint=endpoint,
                             methods=['GET'])  # TODO method from meta info

    def format_result(self, result):
        return format_execution_result(result, default_format_error)

    def _get_field_selection_set(self,
                                 field: graphene.Field,
                                 include_nodes: bool = False) -> Optional[graphql_ast.SelectionSet]:

        return_type = field.type

        if isinstance(return_type, (GraphQLScalarType, GraphQLEnumType)):
            return None

        if isinstance(return_type, GraphQLObjectType):
            # TODO get from fields

            return graphql_ast.SelectionSet(
                selections=[
                    graphql_ast.Field(name=graphql_ast.Name(value='hello'))
                ]
            )

        raise NotImplementedError

    def _get_query_view_func(self, field: graphene.Field, field_name: str):
        schema = self.schema
        field_selection_set = self._get_field_selection_set(field, include_nodes=True)

        def view_func():
            document_ast = graphql_ast.Document(
                [
                    graphql_ast.OperationDefinition(
                        operation='query',
                        selection_set=graphql_ast.SelectionSet(
                            selections=[
                                graphql_ast.Field(
                                    name=graphql_ast.Name(value=field_name),
                                    # TODO get these from get parameters
                                    arguments=[
                                        graphql_ast.Argument(name=graphql_ast.Name(value='name'),
                                                             value=graphql_ast.StringValue(value='foo'))
                                    ],
                                    selection_set=field_selection_set
                                )
                            ]
                        )
                    )
                ]
            )

            execution_results = schema.execute(document_ast)

            # TODO custom encoder that positions data[field_name] at data
            result, status_code = encode_execution_results([execution_results],
                                                           is_batch=False,
                                                           format_error=default_format_error,
                                                           encode=json_encode)

            return Response(result,
                            status=status_code,
                            content_type='application/json')

        return view_func