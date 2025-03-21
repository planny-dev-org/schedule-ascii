import os
import logging
import sqlite3

LOG = logging.getLogger(__name__)


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
            "CREATE TABLE schedule(id INTEGER PRIMARY KEY, start_day, time_span_days)"
        )
        self.cur.execute(
            "CREATE TABLE person(id VARCHAR PRIMARY KEY, activity_rate, night_count, weekend_count, target_hours, holiday_hours, effective_hours, debt_hours)"
        )
        self.cur.execute(
            "CREATE TABLE shift(id VARCHAR PRIMARY KEY, display_name, ascii_display, duration, start_time, end_time)"
        )
        self.cur.execute(
            "CREATE TABLE task(id INTEGER PRIMARY KEY, person_id, shift_id, day, FOREIGN KEY (shift_id) REFERENCES shift(id), FOREIGN KEY (person_id) REFERENCES person(id))"
        )
        self.cur.execute(
            "CREATE TABLE coverage(id INTEGER PRIMARY KEY, min_value, max_value, shift_id, day, FOREIGN KEY (shift_id) REFERENCES shift(id))"
        )
        self.cur.execute(
            "CREATE TABLE preallocation(id INTEGER PRIMARY KEY, shift_id, person_id, type, day, FOREIGN KEY (shift_id) REFERENCES shift(id), FOREIGN KEY (person_id) REFERENCES person(id))"
        )
        self.cur.execute(
            """
            CREATE TABLE shift_label(shift_id VARCHAR,
              label,
              FOREIGN KEY (shift_id) REFERENCES shift(id))
            """
        )
        self.cur.execute(
            """
            CREATE TABLE task_label(task_id INTEGER,
              label,
              FOREIGN KEY (task_id) REFERENCES task(id))
            """
        )
        # Liaison tables
        self.cur.execute(
            """
            CREATE TABLE coverage_person(id INTEGER PRIMARY KEY,
              coverage_id,
              person_id,
              FOREIGN KEY (coverage_id) REFERENCES coverage(id),
              FOREIGN KEY (person_id) REFERENCES person(id))
            """
        )

    def select(self, table, columns, where_close=None):
        request = f"""
            SELECT {','.join(columns)} FROM {table}
        """
        LOG.debug(f"{request} WHERE {where_close}")
        if where_close:
            request = f"{request} WHERE {where_close}"

        return self.cur.execute(request).fetchall()

    def select_person_nights(self):
        """
        Count number of nights for each person
        """
        request = f"""
            SELECT person_id, count(*) FROM task INNER JOIN shift on task.shift_id=shift.id FULL JOIN shift_label ON
            shift.id=shift_label.shift_id WHERE label='night' group by person_id
        """
        LOG.debug(request)
        return self.cur.execute(request).fetchall()

    def select_person_weekends(self):
        """
        Count number of weekends for each person
        """
        request = f"""
            SELECT person_id, count(*) FROM task INNER JOIN task_label ON task_label.task_id=task.id where label='weekend' GROUP BY person_id
        """
        LOG.debug(request)
        return self.cur.execute(request).fetchall()

    def select_person_effective_hours(self):
        """
        Sum effective hours for each person
        """
        request = f"""
            SELECT person_id, sum(duration) FROM task INNER JOIN shift ON shift.id=task.shift_id GROUP BY person_id
        """
        LOG.debug(request)
        return self.cur.execute(request).fetchall()

    def select_person_tasks(self, person_id):
        """
        Count number of weekends for each person
        """

        request = f"""
            SELECT ascii_display, day FROM task INNER JOIN shift ON shift.id=task.shift_id where person_id='{person_id}'
        """
        LOG.debug(request)
        return self.cur.execute(request).fetchall()

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
        return self.cur.execute(request).fetchall()

    def commit(self):
        request = f"""
            COMMIT
            """
        LOG.debug(request)
        self.cur.execute(request)

    def rollback(self):
        request = f"""
            ROLLBACK
            """
        LOG.debug(request)
        self.cur.execute(request).fetchall()
