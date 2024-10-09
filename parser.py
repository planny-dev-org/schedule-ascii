import os
from os import path
import json
import sqlite3
import logging


LOG = logging.getLogger(__name__)


class Parser:
    """
    parse json data and store to an sqlite DB file
    """

    def __init__(self, json_file_path):
        self.json_file_path = path.abspath(json_file_path)

        # load data file
        self.json_data = json.load(self.json_file_path)

        # delete any existing sqlite file
        db_filename = path.join(
                path.dirname(self.json_file_path),
                path.basename(self.json_file_path).replace(".json", "") + ".db",
            )
        try:
            os.remove(db_filename)
            LOG.info(f"file {db_filename} deleted")
        except FileNotFoundError:
            pass

        # init sqlite connector and cursor
        self.con = sqlite3.connect(
            db_filename
        )
        self.cur = self.con.cursor()


    def init_tables(self):
        """
        Create db tables
        :return:
        """
        self.cur.execute("CREATE TABLE person(name, activity_rate, night_shifts, weekend_shifts, shifts, target_hours, holiday_hours, work_hours")
        self.cur.execute("CREATE TABLE day(id, is_night, is_weekend, iso_day)")
        self.cur.execute("CREATE TABLE shift(name, display_name, is_night, duration, start_time, end_time)")
        self.cur.execute("CREATE TABLE person_day_shift(person, day, shift)")





    def store(self):
        """
        Store json data to db tables
        :return:
        """
