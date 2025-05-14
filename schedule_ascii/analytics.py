import datetime
from typing import List

import dataclasses
import math

from schedule_ascii.db import DBAdapter


def iso_time_to_minutes(iso_time):
    """
    Convert a time in the form HH:MM:SS to minutes
    """
    hours, minutes, _ = iso_time.split(":")

    return int(hours) * 3600 + int(minutes)


def standard_deviation(values):
    """
    Return standard deviation given a list of deviation values
    """
    # compute average
    values_size = len(values)
    if not values_size:
        return 0

    average = sum(values) / values_size

    std_deviation_term = 0
    for value in values:
        deviation = value - average
        std_deviation_term += deviation**2
    try:
        return round(math.sqrt(std_deviation_term / values_size), 1)
    except ZeroDivisionError:
        return 0.0


@dataclasses.dataclass
class DBAnalytics:
    db_adapter: DBAdapter


@dataclasses.dataclass
class PersonAnalytics(DBAnalytics):
    available_days: List[int] = dataclasses.field(default_factory=list)
    available_work_hours: int = 0


@dataclasses.dataclass
class ScheduleAnalytics(DBAnalytics):

    time_span: int = 0  # schedule time span in days
    min_coverage_work_hours: float = 0  # minimum hours needed to fulfill min coverage
    max_coverage_work_hours: float = 0  # minimum hours needed to fulfill max coverage
    # available working hours all people can provide counting 8 hours per working day, do not handle day exclusions
    available_work_hours: float = 0
    total_work_hours: float = 0
    weekend_days: List[int] = dataclasses.field(default_factory=list)

    def compute(self):
        self.time_span = self.db_adapter.select("schedule", ["time_span_days"])[0][0]

        for min_value, max_value, shift_id in self.db_adapter.select(
            "coverage", ["min_value", "max_value", "shift_id"]
        ):
            shift_duration = self.db_adapter.select(
                "shift", ["duration"], f"id='{shift_id}'"
            )[0][0]
            self.min_coverage_work_hours += min_value * shift_duration
            self.max_coverage_work_hours += max_value * shift_duration

        for person in self.db_adapter.select("person", ["id"]):
            person_id = person[0]
            for day in range(self.time_span):
                if not len(
                    self.db_adapter.cur.execute(
                        f"SELECT id FROM preallocation WHERE day={day} AND person_id='{person_id}' AND shift_id in ('OFF', 'HOL')"
                    ).fetchall()
                ):
                    self.available_work_hours += 8

        self.total_work_hours = self.db_adapter.select_total_effective_hours() or 0

        iso_day = datetime.date.fromisoformat(
            self.db_adapter.select("schedule", ["start_day"])[0][0]
        )
        if iso_day.weekday() in [5, 6]:
            self.weekend_days.append(0)
        for day_int in range(1, self.time_span):
            iso_day = iso_day + datetime.timedelta(days=day_int)
            if iso_day.weekday() in [5, 6]:
                self.weekend_days.append(day_int)

    def days_int(self, weekday, start_day=0):
        """
        return all days that match weekday starting from start_day
        :param weekday: 0 to 6 week day
        :param start_day: 0 to time_span, start searching from this day
        :return: List of day integers
        """
        days_int = []
        start_day_str, time_span = self.db_adapter.select(
            "schedule", ["start_day", "time_span_days"]
        )[0]
        start_day_iso = datetime.date.fromisoformat(start_day_str)
        for day_int in range(start_day, time_span):
            iso_day = start_day_iso + datetime.timedelta(days=day_int)
            if iso_day.weekday() == weekday:
                days_int.append(day_int)

        return days_int

    def target_int_days(self):
        """
        Return available work days in the schedule
        A work day is any day that is not a weekend nor a bank holiday
        """
        start_date, days_count = self.db_adapter.select(
            "schedule", ["start_day", "time_span_days"]
        )[0]
        start_date = datetime.date.fromisoformat(start_date)
        bank_holidays = self.db_adapter.select("bank_holiday", ["day"])
        target_int_days = []
        for i in range(days_count):
            iso_day = start_date + datetime.timedelta(days=i)
            if (
                iso_day.weekday() not in [5, 6]
                and iso_day.isoformat() not in bank_holidays
            ):
                target_int_days.append(i)

        return target_int_days


@dataclasses.dataclass
class FlawsAnalytic(DBAnalytics):

    name: str = ""
    flaws_min: int = 0  # minimum possible flaws given hard rules
    flaws: int = 0  # number of flaws in the schedule
    flaws_max: int = 0  # maximum number of flaws
    score: int = 0  # analytics score in percentage

    def compute_score(self):
        """
        default method to compute score
        equals to 100 - percentage of flaws (100 * flaws / sample_size)
        :return:
        """
        return 100 - (100 * (self.flaws / self.flaws_max))


@dataclasses.dataclass
class HoursDeviation(FlawsAnalytic):
    """
    Estimate distribution equity of workload among people
    """

    people: List[str] = dataclasses.field(default_factory=list)

    def compute(self):
        deviations = []
        max_deviations = []
        people_str = [f"'{person}'" for person in self.people]
        for effective, target in self.db_adapter.select(
            "person",
            ["effective_hours", "target_hours"],
            f"id IN ({','.join(people_str)})",
        ):
            deviations.append(target - effective)
            max_deviations.extend([target, 0])

        self.flaws = round(standard_deviation(deviations), 0)
        self.flaws_max = round(standard_deviation(max_deviations), 0)

        if self.flaws_max:
            self.score = round(100 - (100 * (self.flaws / self.flaws_max)), 0)


@dataclasses.dataclass
class ExtraHours(FlawsAnalytic):
    """
    Estimate global extra hours
    """

    def compute(self):
        schedule_analytics = ScheduleAnalytics(self.db_adapter)
        schedule_analytics.compute()

        self.flaws_min = max(
            0,
            round(
                schedule_analytics.min_coverage_work_hours
                - schedule_analytics.available_work_hours
            ),
        )
        self.flaws = max(
            0,
            round(
                schedule_analytics.total_work_hours
                - schedule_analytics.min_coverage_work_hours
            ),
        )
        self.flaws_max = max(
            0,
            round(
                schedule_analytics.available_work_hours
                - schedule_analytics.min_coverage_work_hours
            ),
        )

        if self.flaws_max:
            self.score = round(100 - (100 * (self.flaws / self.flaws_max)), 0)


@dataclasses.dataclass
class ShiftFairness(FlawsAnalytic):
    """
    Estimate distribution equity of given shift for given days among people
    """

    people: List[str] = dataclasses.field(default_factory=list)
    shift: str = ""
    days: List[int] = dataclasses.field(default_factory=list)

    def compute(self):
        schedule_analytics = ScheduleAnalytics(self.db_adapter)
        schedule_analytics.compute()

        if not self.days:
            self.days = [day_int for day_int in range(schedule_analytics.time_span)]

        shift_count = len(
            self.db_adapter.select_shift_tasks(self.shift, days=self.days)
        )
        average = round(shift_count / len(self.people), 1)
        low_average = int(average)
        if average - low_average:
            high_average = low_average + 1
        else:
            high_average = low_average

        self.flaws_max = shift_count - high_average

        for person in self.people:
            shift_tasks = self.db_adapter.select_shift_tasks(self.shift, person=person)
            if shift_tasks:
                task_count = len(shift_tasks)
                if task_count >= high_average:
                    self.flaws += task_count - high_average
                else:
                    self.flaws += low_average - task_count

        if self.flaws_max:
            self.score = round(100 - (100 * (self.flaws / self.flaws_max)), 0)


@dataclasses.dataclass
class Sequences(FlawsAnalytic):
    """
    Estimate quality of sequences
    """

    def compute(self):
        schedule_analytics = ScheduleAnalytics(self.db_adapter)
        schedule_analytics.compute()

        sequences = self.db_adapter.select(
            "sequence", ["id", "shift_id", "seq_group", "seq_order", "weekday"]
        )
        groups = set([sequence[2] for sequence in sequences])
        for group in groups:
            sequences = self.db_adapter.select(
                "sequence",
                ["id", "shift_id", "seq_group", "seq_order", "weekday"],
                f"seq_group={group}",
                "seq_order",
            )
            # establish all sequences of integer days
            if sequences:
                int_days_sequences = []

                # init a list of [weekdays, offset to next weekday, shift] in order to iterate over schedule period
                # index 4 is weekday, index 1 is shift
                weekdays_offsets = [
                    [sequence[4], None, sequence[1]] for sequence in sequences
                ]
                weekday = weekdays_offsets[0][0]
                for pos in range(len(weekdays_offsets) - 1):
                    next_weekday = weekdays_offsets[pos + 1][0]
                    offset = next_weekday - weekday
                    offset = (
                        (7 - abs(offset)) if offset < 0 else offset
                    )  # handle case where next weekday is less than weekday
                    weekdays_offsets[pos][1] = offset
                    weekday = next_weekday

                # get first sequence int day and associated weekday_offset
                min_int_day = 999999
                weekday_offsets_pos = -1
                for i, (weekday, offset, shift) in enumerate(weekdays_offsets):
                    int_day = schedule_analytics.days_int(weekday)
                    if int_day and int_day[0] < min_int_day:
                        min_int_day = int_day[0]
                        weekday_offsets_pos = i

                # iterate over schedule days to establish int_days_sequences
                int_day = min_int_day

                if weekday_offsets_pos > -1:
                    current_int_days_sequence = []
                    while True:
                        # add current int day to current sequence
                        current_int_days_sequence.append(
                            [int_day, weekdays_offsets[weekday_offsets_pos][2]]
                        )

                        # then iterate over offsets to get next day
                        offset = weekdays_offsets[weekday_offsets_pos][1]
                        if offset is None:
                            # sequence is finished, append it to int_days_sequences
                            # reboot position and set int_day to next sequence weekday int day
                            int_days_sequences.append(current_int_days_sequence)
                            weekday_offsets_pos = 0
                            current_int_days_sequence = []
                            try:
                                int_day = schedule_analytics.days_int(
                                    weekdays_offsets[0][0], start_day=int_day
                                )[0]
                            except IndexError:
                                # next int day is outside schedule, exit loop
                                break
                        else:
                            # continue current sequence if int_day still in schedule time span
                            # increment weekday_offsets_pos and int_day
                            int_day += offset
                            weekday_offsets_pos += 1
                            if int_day > schedule_analytics.time_span:
                                # exit loop, append sequence and break
                                int_days_sequences.append(current_int_days_sequence)
                                break

                # estimate flaws for each sequence and person
                for int_days_sequence in int_days_sequences:
                    people = []
                    min_coverage = 0
                    for day_int, shift in int_days_sequence:
                        min_coverage = max(
                            min_coverage,
                            len(
                                self.db_adapter.select(
                                    "task",
                                    ["id"],
                                    where_close=f"shift_id='{shift}' AND day={day_int}",
                                )
                            ),
                        )  # add max in case coverage is not constant, which should not happens
                        people.extend(
                            [
                                person[0]
                                for person in self.db_adapter.select(
                                    "task",
                                    ["person_id"],
                                    where_close=f"shift_id='{shift}' AND day={day_int}",
                                )
                            ]
                        )

                    person_count = len(set(people))
                    # no flaw = only as many person are doing all the tasks as min coverage
                    # max flaw = as much person as sequence length minus min coverage
                    self.flaws_max += person_count
                    self.flaws += abs(min_coverage - person_count)

        if self.flaws_max:
            self.score = round(100 - (100 * (self.flaws / self.flaws_max)), 0)


@dataclasses.dataclass
class WeekWorktime(FlawsAnalytic):
    """
    Estimate quality of week worktime
    """

    max_worktime_minutes: int = 50 * 3600  # 50 hours

    def compute(self):
        time_span = self.db_adapter.select("schedule", ["time_span_days"])[0][0]
        schedule_analytics = ScheduleAnalytics(self.db_adapter)

        try:
            first_monday_int = schedule_analytics.days_int(0)[0]  # 0: Monday
        except IndexError:
            return

        for person in self.db_adapter.select("person", ["id"]):
            day = first_monday_int
            while day < time_span:
                # fetch working time for the week
                tasks = self.db_adapter.select_person_tasks(
                    person[0], days=[a for a in range(day, day + 7)]
                )
                duration = sum([duration for _, _, duration, _, _ in tasks])

                # add previous day task duration from midnight to end_time (if exists)
                previous_day_tasks = self.db_adapter.select_person_tasks(
                    person[0], days=[day - 1]
                )
                for _, _, _, start_time, end_time in previous_day_tasks:
                    start_time = iso_time_to_minutes(start_time)
                    end_time = iso_time_to_minutes(end_time)
                    if start_time > end_time:
                        duration -= (
                            24 * 3600
                        ) - start_time  # remove time from start_time to midnight on previous day

                # remove last day task duration after midnight (if exists)
                last_day_tasks = self.db_adapter.select_person_tasks(
                    person[0], days=[day - 1]
                )
                for _, _, _, start_time, end_time in last_day_tasks:
                    start_time = iso_time_to_minutes(start_time)
                    end_time = iso_time_to_minutes(end_time)
                    if start_time > end_time:
                        duration -= end_time  # remove the night part above midnight on the last day

                if duration > self.max_worktime_minutes:
                    self.flaws += 1

                self.flaws_max += 1
                day = day + 7

        if self.flaws_max:
            self.score = round(100 - (100 * (self.flaws / self.flaws_max)), 0)


@dataclasses.dataclass
class WorkerPreference(FlawsAnalytic):
    """
    Estimate quality of week worktime
    Every time a shift is attributed to a person that is not in primary nor secondary group, it counts for 3 flaws
    Every time a shift is attributed to a person that is not in primary group, it counts for 1 flaw
    """

    primary_people: List[str] = dataclasses.field(default_factory=list)
    secondary_people: List[str] = dataclasses.field(default_factory=list)
    shift: str = ""
    # TODO: see if weekdays is needed
    #    weekdays: List[int] = dataclasses.field(default_factory=list)

    def compute(self):
        # if all shifts are attributed to people other than primary or secondary groups, then
        # max flaw count is equal to the max number of shift that can be attributed
        schedule_analytics = ScheduleAnalytics(self.db_adapter)
        days_int = [day for day in range(schedule_analytics.time_span)]

        coverages = self.db_adapter.select(
            "coverage",
            ["max_value"],
            f"shift_id='{self.shift}'",
        )
        self.flaws_max = 3 * sum([max_val[0] for max_val in coverages])

        # estimate minimum flaws. Whenever all primary people are not available for 1 day,
        # it increases by 1 the min flaws
        for day_int in days_int:
            primary_people_unavailable = True
            for person in self.primary_people:
                if not len(
                    self.db_adapter.select_person_preals(person, [day_int])
                ) or not len(
                    self.db_adapter.select_person_exclusions(
                        person, shift_id=self.shift, days=[day_int]
                    )
                ):
                    primary_people_unavailable = False
                    break

            if primary_people_unavailable:
                self.flaws_min += 1

        # estimate flaws
        tasks = self.db_adapter.select_shift_tasks(shift_id=self.shift)
        for task, person in tasks:
            if person in self.primary_people:
                flaw = 0
            elif person in self.secondary_people:
                flaw = 1
            else:
                flaw = 3

            self.flaws += flaw

        if self.flaws_max:
            self.score = round(100 - (100 * (self.flaws / self.flaws_max)), 0)
