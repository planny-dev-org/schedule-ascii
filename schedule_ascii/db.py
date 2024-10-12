import os
import logging
import sqlite3

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)


class DBAdapter:
    """
    Singleton class that handles database
    """

    def __init__(self, db_filename):

        # delete any existing sqlite file
        try:
            os.remove(db_filename)
            LOG.info(f"file {db_filename} deleted")
        except FileNotFoundError:
            pass

        # init sqlite connector and cursor
        self.con = sqlite3.connect(db_filename)
        self.cur = self.con.cursor()

    def init_tables(self):
        """
        Create db tables
        :return:
        """
        # base resources
        self.cur.execute(
            "CREATE TABLE person(id VARCHAR PRIMARY KEY, activity_rate, night_shifts, weekend_shifts, target_hours, holiday_hours, work_hours, debt_hours)"
        )
        self.cur.execute(
            "CREATE TABLE shift(id VARCHAR PRIMARY KEY, display_name, ascii_display, duration, start_time, end_time)"
        )
        self.cur.execute(
            "CREATE TABLE task(id INTEGER PRIMARY KEY, person_id, shift_id, day, FOREIGN KEY (shift_id) REFERENCES shift(id), FOREIGN KEY (person_id) REFERENCES person(id))"
        )

        # foreign table resources (labels)
        self.cur.execute(
            "CREATE TABLE shift_labels(shift_id VARCHAR, label, FOREIGN KEY (shift_id) REFERENCES shift(id))"
        )
        self.cur.execute(
            "CREATE TABLE task_labels(task_id INTEGER, label, FOREIGN KEY (task_id) REFERENCES task(id))"
        )

    def select(self, table, columns, where_close=None):
        request = f"""
            SELECT {','.join(columns)} FROM {table}
        """
        if where_close:
            request = f"{request} WHERE {where_close}"

        LOG.debug(request)
        return self.cur.execute(request)

    def insert(self, table, values):
        request = f"""
            INSERT INTO {table} values {str(values)}
            """
        LOG.debug(request)
        return self.cur.execute(request)

    def update(self, table, where_close, set_close):
        request = f"""
            UPDATE {table} SET {set_close} WHERE {where_close} 
            """
        LOG.debug(request)
        return self.cur.execute(request)
