from typing import List, Optional, Dict

class SQLAPI:
    def _api_description(self) -> str:
        return ""
    
    def select(
        table_name: str,
        columns: Optional[List[str]],
        conditions: Optional[List[Dict[str, str]]] = None,
        order_by: Optional[List[str]] = None,
        desc: Optional[bool] = False,
        limit: Optional[int] = None,
        top: Optional[int] = None,
        join: Optional[dict] = None,
        group_by: Optional[str] = None
    ) -> str:
        """
        Select rows from a table with specified columns and conditions.

        Args:
            table_name (str): The name of a table to query. 
            columns (List[str]): A list of column names to select. If * is given, all columns are selected. The column input order matters and must be alphabetically sorted as the arguments of the function.
            conditions (List[Dict[str, str]], optional): A list of conditions in the form: [{'operator': 'AND', 'left': 'column_name', 'sign': '=', 'right': 'value'}]. Operators can be AND, OR. Signs can be =, !=, <, >, <=, >=. The dictionary keys must be presented in the order of 'operator', 'left', 'sign', 'right'.
                - operator (str): The operator to use for the condition. Can be 'AND' or 'OR'.
                - left (str): The left side of the condition.
                - sign (str): The sign of the condition. Can be '=', '!=', '<', '>', '<=', '>='.
                - right (str): The right side of the condition.
            order_by (List[str], optional): A list of columns to order the result by.
            desc (bool, optional): If order_by is specified, this flag indicates whether to sort in descending order. Default is False.
            limit (int, optional): The maximum number of rows to return.
            top (int, optional): The maximum number of rows to return.
            join (Dict, optional): A dictionary containing the join_type, table_name, and join_condition. Join types can be INNER, LEFT, RIGHT, FULL, CROSS, NATURAL. Join conditions are in the form: 'table1.column1 = table2.column2'.
            group_by (str, optional): The column to group the results by.
                - join_type (str): The type of join to perform. Can be 'INNER', 'LEFT', 'RIGHT', 'FULL', 'CROSS', 'NATURAL'.
                - table_name (str): The name of the table to join.
                - join_condition (str): The condition to join the tables on.
        Returns:
            str: The constructed SQL SELECT query.
        """
        cols_str = ", ".join(columns)
        where_clause = ""
        if conditions:
            condition_strings = [
                f"{cond['left']} {cond['sign']} '{cond['right']}'" for cond in conditions
            ]
            where_clause = " WHERE " + f" {conditions[0]['operator']} ".join(condition_strings)
        order_clause = f" ORDER BY {', '.join(order_by)}" if order_by else ""
        if desc:
            order_clause += " DESC"
        else:
            order_clause += " ASC"
        limit_clause = f" LIMIT {limit}" if limit else ""
        top_clause = f" TOP {top}" if top else ""
        join_clause = ""
        if join:
            join_clause = f" {join['join_type']} JOIN {join['table_name']} ON {join['join_condition']}"
        group_by_clause = f" GROUP BY {group_by}" if group_by else ""
        return f"SELECT {cols_str} FROM {table_name}{where_clause}{order_clause}{limit_clause}{top_clause}{join_clause}{group_by_clause};"


    def insert(
        table_name: str,
        columns: List[str],
        values: List[List[str]]
    ) -> str:
        """
        Insert rows of data into a table with specified columns.    

        Args:
            table_name (str): The name of the table to insert into.
            columns (List[str]): A list of column names for the INSERT operation. The column input order matters and must be alphabetically sorted as the arguments of the function.
            values (List[List[str]]): A list of rows, where each row is a list of values to insert.

        Returns:
            str: The constructed SQL INSERT query.
        """
        cols_str = f"({', '.join(columns)})"
        values_str = ", ".join([f"({', '.join([repr(val) for val in row])})" for row in values])
        return f"INSERT INTO {table_name} {cols_str} VALUES {values_str};"


    def update(
        table_name: str,
        columns: List[str],
        values: List[str],
        conditions: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Update rows in a table with specified columns and values.

        Args:
            table_name (str): The name of the table to update.
            columns (List[str]): A list of column names to update. The column input order matters and must be alphabetically sorted as the arguments of the function.
            values (List[str]): A list of corresponding values to update.
            conditions (List[Dict[str, str]], optional): A list of conditions in the form: [{'operator': 'AND', 'left': 'column_name', 'sign': '=', 'right': 'value'}]. Operators can be AND, OR. Signs can be =, !=, <, >, <=, >=. The dictionary keys must be presented in the order of 'operator', 'left', 'sign', 'right'.
                - operator (str): The operator to use for the condition. Can be 'AND' or 'OR'.
                - left (str): The left side of the condition.
                - sign (str): The sign of the condition. Can be '=', '!=', '<', '>', '<=', '>='.
                - right (str): The right side of the condition.

        Returns:
            str: The constructed SQL UPDATE query.
        """
        set_clause = ", ".join([f"{col} = '{val}'" for col, val in zip(columns, values)])
        where_clause = ""
        if conditions:
            condition_strings = [
                f"{cond['left']} {cond['sign']} '{cond['right']}'" for cond in conditions
            ]
            where_clause = " WHERE " + f" {conditions[0]['operator']} ".join(condition_strings)
        return f"UPDATE {table_name} SET {set_clause}{where_clause};"


    def delete(
        table_name: str,
        conditions: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Delete rows from a table based on given conditions.

        Args:
            table_name (str): The name of the table to delete from.
            conditions (List[Dict[str, str]], optional): A list of conditions in the form:[{'operator': 'AND', 'left': 'column_name', 'sign': '=', 'right': 'value'}]. Operators can be AND, OR. Signs can be =, !=, <, >, <=, >=. The dictionary keys must be presented in the order of 'operator', 'left', 'sign', 'right'.
                - operator (str): The operator to use for the condition. Can be 'AND' or 'OR'.
                - left (str): The left side of the condition.
                - sign (str): The sign of the condition. Can be '=', '!=', '<', '>', '<=', '>='.
                - right (str): The right side of the condition.
        Returns:
            str: The constructed SQL DELETE query.
        """
        where_clause = ""
        if conditions:
            condition_strings = [
                f"{cond['left']} {cond['sign']} '{cond['right']}'" for cond in conditions
            ]
            where_clause = " WHERE " + f" {conditions[0]['operator']} ".join(condition_strings)
        return f"DELETE FROM {table_name}{where_clause};"


    def create(
        table_name: str,
        columns: List[str],
        column_types: List[str]
    ) -> str:
        """
        Create a table with specified columns.

        Args:
            table_name (str): The name of the table to create.
            columns (List[str]): A list of column definitions, e.g., ['column1', 'column2']. The column input order matters and must be alphabetically sorted as the arguments of the function.
            column_types (List[str]): A list of column types, e.g., ['INT', 'VARCHAR(255)']. If a column type is not specified, it defaults to VARCHAR(255).

        Returns:
            str: The constructed SQL CREATE query.
        """
        return f"CREATE TABLE {table_name} ({', '.join([f'{col} {col_type}' for col, col_type in zip(columns, column_types)])});"