from typing import Optional

import flask
import graphene
import graphql.language.ast as graphql_ast
from flask import Response
from graphene.test import format_execution_result, default_format_error
from graphql import GraphQLScalarType, GraphQLEnumType, GraphQLObjectType
from graphql_server import encode_execution_results, json_encode
from flask import request

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
        if query_type:
            print(query_type, query_type.fields)
            for field_name, field in query_type.fields.items():
                endpoint = f'query.{query_type.name}.{field_name}'

                app.add_url_rule(f'/{field_name}',
                                 view_func=self._get_query_view_func(field, field_name),
                                 endpoint=endpoint,
                                 methods=['GET'])  # TODO method from meta info

        mutation_type = self.schema.get_mutation_type()
        if mutation_type:
            for field_name, field in mutation_type.fields.items():
                endpoint = f'mutation.{mutation_type.name}.{field_name}'

                app.add_url_rule(f'/{field_name}',
                                 view_func=self._get_mutation_view_func(field, field_name),
                                 endpoint=endpoint,
                                 methods=['POST'])  # TODO method from meta info

    def format_result(self, result):
        return format_execution_result(result, default_format_error)

    def _get_field_selection_set(self,
                                 field: graphene.Field,
                                 include_nodes: bool = False) -> Optional[graphql_ast.SelectionSet]:

        return_type = field.type
        if isinstance(return_type, (GraphQLScalarType, GraphQLEnumType)):
            return None
        elif isinstance(return_type, GraphQLObjectType):
            # selections = []
            # for sub_field in

            return graphql_ast.SelectionSet(
                selections=[
                    graphql_ast.Field(name=graphql_ast.Name(value=name), selection_set=self._get_field_selection_set(sub_field, include_nodes)) for name, sub_field in field.type.fields.items()

                    # graphql_ast.Field(name=graphql_ast.Name(value='hello'))
                ]
            )

        raise NotImplementedError

    def _get_query_view_func(self, field: graphene.Field, field_name: str):
        schema = self.schema
        field_selection_set = self._get_field_selection_set(field, include_nodes=True)
        variable_definitions = []
        arguments = []

        for arg_name, arg_definition in field.args.items():
            variable = graphql_ast.Variable(name=graphql_ast.Name(value=arg_name))
            arguments.append(graphql_ast.Argument(name=graphql_ast.Name(value=arg_name), value=variable))
            variable_definitions.append(graphql_ast.VariableDefinition(
                variable=variable,
                type=graphql_ast.NamedType(name=graphql_ast.Name(value=arg_definition.type.name)),
                # default_value=graphql_ast.Value(value=arg_definition.default_value)
            ))

        def view_func():
            document_ast = graphql_ast.Document(
                [
                    graphql_ast.OperationDefinition(
                        operation='query',
                        variable_definitions=variable_definitions,
                        selection_set=graphql_ast.SelectionSet(
                            selections=[
                                graphql_ast.Field(
                                    name=graphql_ast.Name(value=field_name),
                                    arguments=arguments,
                                    selection_set=field_selection_set
                                )
                            ]
                        )
                    )
                ]
            )

            variable_values = request.args

            execution_results = schema.execute(
                document_ast,
                variable_values=variable_values
            )

            # TODO custom encoder that positions data[field_name] at data
            result, status_code = encode_execution_results([execution_results],
                                                           is_batch=False,
                                                           format_error=default_format_error,
                                                           encode=json_encode)

            return Response(result,
                            status=status_code,
                            content_type='application/json')

        return view_func

    def _get_mutation_view_func(self, field: graphene.Field, field_name: str):
        schema = self.schema
        field_selection_set = self._get_field_selection_set(field, include_nodes=True)
        variable_definitions = []
        arguments = []

        for arg_name, arg_definition in field.args.items():
            variable = graphql_ast.Variable(name=graphql_ast.Name(value=arg_name))
            arguments.append(graphql_ast.Argument(name=graphql_ast.Name(value=arg_name), value=variable))
            variable_definitions.append(graphql_ast.VariableDefinition(
                variable=variable,
                type=graphql_ast.NamedType(name=graphql_ast.Name(value=arg_definition.type.name)),
                default_value=arg_definition.default_value
            ))

        def view_func():
            document_ast = graphql_ast.Document(
                [
                    graphql_ast.OperationDefinition(
                        operation='mutation',
                        variable_definitions=variable_definitions,
                        selection_set=graphql_ast.SelectionSet(
                            selections=[
                                graphql_ast.Field(
                                    name=graphql_ast.Name(value=field_name),
                                    arguments=arguments,
                                    selection_set=field_selection_set
                                )
                            ]
                        )
                    )
                ]
            )

            variable_values = request.json

            execution_results = schema.execute(
                document_ast,
                variable_values=variable_values
            )

            # TODO custom encoder that positions data[field_name] at data
            result, status_code = encode_execution_results([execution_results],
                                                           is_batch=False,
                                                           format_error=default_format_error,
                                                           encode=json_encode)

            return Response(result,
                            status=status_code,
                            content_type='application/json')

        return view_func
