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
            """
            CREATE TABLE preallocation(id INTEGER PRIMARY KEY, shift_id, person_id, day, FOREIGN KEY (shift_id) REFERENCES shift(id), FOREIGN KEY (person_id) REFERENCES person(id))
            """
        )
        self.cur.execute(
            "CREATE TABLE exclusion(id INTEGER PRIMARY KEY, shift_id, person_id, day, FOREIGN KEY (shift_id) REFERENCES shift(id), FOREIGN KEY (person_id) REFERENCES person(id))"
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
        # Airtable people are skipped, it's an objective in new schedule version
        self.cur.execute(
            """
            CREATE TABLE sequence(id INTEGER PRIMARY KEY,
              shift_id,
              seq_group,
              seq_order,
              weekday,
              FOREIGN KEY (shift_id) REFERENCES shift(id))
            """
        )

        # indexes
        self.cur.execute(
            "CREATE INDEX preallocation_idx ON preallocation(person_id, day)"
        )
        self.cur.execute("CREATE INDEX task_idx ON task(person_id, day)")
        self.cur.execute("CREATE INDEX coverage_idx ON coverage(shift_id, day)")
        self.cur.execute(
            "CREATE INDEX exclusion_idx ON exclusion(person_id, day, shift_id)"
        )
        self.cur.execute(
            "CREATE INDEX coverage_person_idx ON coverage_person(coverage_id, person_id)"
        )

    def select(
        self, table, columns, where_close=None, order_by_close=None, group_by_close=None
    ):
        request = f"""
            SELECT {','.join(columns)} FROM {table}
        """
        if where_close:
            request = f"{request} WHERE {where_close}"

        if group_by_close:
            request = f"{request} GROUP BY {group_by_close}"

        if order_by_close:
            request = f"{request} ORDER BY {order_by_close}"
        LOG.debug(f"{request}")

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
            SELECT person_id, count(*) FROM task INNER JOIN task_label ON task_label.task_id=task.id WHERE label='weekend' GROUP BY person_id
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

    def select_total_effective_hours(self):
        """
        Sum of all effective hours in the schedule
        """
        request = f"""
            SELECT sum(duration) FROM task INNER JOIN shift ON shift.id=task.shift_id
        """
        LOG.debug(request)
        return self.cur.execute(request).fetchall()[0][0]

    def select_person_tasks(self, person_id, days=None):
        """
        Select person tasks
        """
        request = f"""
            SELECT ascii_display, day, duration, start_time, end_time FROM task INNER JOIN shift ON shift.id=task.shift_id WHERE person_id='{person_id}'
        """
        if days:
            request = f"{request} AND day IN ({','.join([str(day) for day in days])})"

        LOG.debug(request)
        return self.cur.execute(request).fetchall()

    def select_shift_tasks(self, shift_id, days=None, person=""):
        """
        Select shift tasks
        """
        request = f"""
            SELECT task.id, task.person_id FROM task INNER JOIN shift ON shift.id=task.shift_id WHERE shift_id='{shift_id}'
        """
        if days:
            request += f"AND day IN ({','.join([str(day) for day in days])})"
        if person:
            request += f"AND person_id='{person}'"

        LOG.debug(request)
        return self.cur.execute(request).fetchall()

    def select_person_preals(self, person_id, days=None):
        """
        Select person preallocations
        """
        request = f"""
            SELECT ascii_display, day FROM preallocation INNER JOIN shift ON shift.id=preallocation.shift_id WHERE person_id='{person_id}'
        """
        if days:
            request = f"{request} AND day IN ({','.join(days)})"
        LOG.debug(request)
        return self.cur.execute(request).fetchall()

    def select_person_exclusions(self, person_id, shift_id="", days=None):
        """
        Select person exclusions
        """
        request = f"""
            SELECT shift_id, day FROM exclusion WHERE person_id='{person_id}'
        """
        if shift_id:
            request = f"{request} AND shift_id={shift_id}"
        if days:
            request = f"{request} AND day IN ({','.join(days)})"
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
        try:
            self.cur.execute(request)
        except sqlite3.OperationalError:
            # avoid crash if no transaction is active
            pass

    def rollback(self):
        request = f"""
            ROLLBACK
            """
        LOG.debug(request)
        self.cur.execute(request).fetchall()
