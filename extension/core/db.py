import psycopg2
from psycopg2.pool import ThreadedConnectionPool
import threading
from contextlib import contextmanager
import sqlite3
import tenacity
from tenacity import retry_if_exception_type, wait_random_exponential
import json
from typing import Optional, List
from extension.core.definitions import ParsedGameState, Execution, Step, DataPoint


class SQLliteDBClient:
    def __init__(
        self,
        min_connections: int = 5,
        max_connections: int = 20,
        **db_config,
    ):
        self._pool = None
        self.min_connections = min_connections
        self.max_connections = max_connections
        self._lock = threading.Lock()
        self.db_config = db_config
        self.database_file = self.db_config.get("database_file")

    async def initialize(self):
        """Initialize the connection pool"""
        if self._pool is None:
            async with self._lock:
                if self._pool is None:  # Double check pattern
                    self._pool = ThreadedConnectionPool(
                        self.min_connections, self.max_connections, **self.db_config
                    )

    @contextmanager
    def get_connection(self):
        """Context manager for SQLite database connections"""
        conn = None
        try:
            conn = sqlite3.connect(self.database_file)
            yield conn
        finally:
            if conn:
                conn.close()

    async def get_resume_state(
        self, collection_id, step_number=None
    ) -> tuple[
        Optional[Step],
        Optional[ParsedGameState],
        Optional[List[Execution]],
    ]:
        """Get the state to resume from"""
        try:
            # Get most recent successful program to resume from
            with self.get_connection() as conn:
                cur = conn.cursor()

                if step_number is not None:
                    cur.execute(
                        """
                    SELECT * FROM data_points
                    WHERE collection_id = ?
                    AND step_number = ?
                    ORDER BY step_number DESC
                    LIMIT 1
                    """,
                        (collection_id, step_number),
                    )
                else:
                    cur.execute(
                        """
                    SELECT * FROM data_points
                    WHERE collection_id = ?
                    ORDER BY step_number DESC
                    LIMIT 1
                    """,
                        (collection_id,),
                    )

                results = cur.fetchall()

            if not results:
                print(f"No valid data points found for collection_id {collection_id}")
                return None, None, None

            row = dict(zip([desc[0] for desc in cur.description], results[0]))

            step = Step(
                number=row["step_number"],
                instruction=row["instruction"],
                iteration_number=row["iteration_number"],
                in_iteration_number=row["in_iteration_number"],
            )
            game_state = ParsedGameState.from_dict(
                json.loads(row["evaluated_game_state_json"])
            )
            execution_history = [
                Execution.from_dict(e)
                for e in json.loads(row["execution_history_json"])
            ]

            return step, game_state, execution_history

        except Exception as e:
            print(f"Error getting resume state: {e}")
            return None, None, None

    @tenacity.retry(
        retry=retry_if_exception_type(
            (psycopg2.OperationalError, psycopg2.InterfaceError, psycopg2.DatabaseError)
        ),
        wait=wait_random_exponential(multiplier=1, min=4, max=10),
    )
    async def create_data_point(self, data_point: DataPoint):
        """Create a new program, now with connection management"""
        with self.get_connection() as conn:
            try:
                cur = conn.cursor()

                # Insert the program data
                cur.execute(
                    """
                    INSERT INTO data_points (
                        runtime_version,
                        collection_id,
                        step_number,
                        instruction,
                        iteration_number,
                        in_iteration_number,
                        input_game_state_json,
                        execution_history_json,
                        agent_name,
                        agent_output_json,
                        evaluation_json,
                        evaluated_game_state_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        data_point.runtime_version,
                        data_point.collection_id,
                        data_point.step.number,
                        data_point.step.instruction,
                        data_point.step.iteration_number,
                        data_point.step.in_iteration_number,
                        json.dumps(data_point.input_game_state.to_dict()),
                        json.dumps([e.to_dict() for e in data_point.execution_history]),
                        data_point.agent_name,
                        json.dumps(data_point.agent_output.to_dict()),
                        json.dumps(data_point.evaluation.to_dict()),
                        json.dumps(data_point.evaluated_game_state.to_dict()),
                    ),
                )

                conn.commit()

            except Exception as e:
                conn.rollback()
                print(f"Error creating data_point: {e}")
                raise e
