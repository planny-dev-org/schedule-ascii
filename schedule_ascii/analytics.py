import datetime
from typing import List

import dataclasses
import math

from db import DBAdapter


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


def hours_score(values):
    """
    Compute a score from 0 to 100 for hours targets
    formula: 100 - total sum of deviation divided by total sum of target, in percentage
    maximum deviation factor is caped to 1

    :param values: list of tuples [(delta, target), ...]
    :return:
    """
    target_values = []
    delta_values = []

    for value in values:
        delta_values.append(value[0])
        target_values.append(value[1])
    total_delta = sum(delta_values)
    total_target = sum(target_values)
    try:
        return (
            total_delta,
            total_target,
            round(100 - (100 * min(total_delta / total_target, 1)), 1),
        )
    except ZeroDivisionError:
        return total_delta, total_target, 0.0


def fairness_score(values):
    """
    Compute a score of fairness from 0 to 100 for
    formula: score = 100 - total sum of deviation divided by total sum of target, in percentage

    :param values: list of tuples [(delta, target), ...]
    :return:
    """
    if not values:
        return 0, 0.0

    total_sum = sum(values)
    mean = total_sum / len(values)
    total_deviation = sum([abs(value - mean) for value in values])
    try:
        return total_deviation, round(
            100 - (100 * min(total_deviation / total_sum, 1)), 1
        )
    except ZeroDivisionError:
        return total_deviation, 0.0


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
        self.time_span = self.db_adapter.select("schedule", ["time_span_days"])[0]

        for min_value, max_value, shift_id in self.db_adapter.select(
            "coverage", ["min_value", "max_value", "shift_id"]
        ):
            shift_duration = self.db_adapter.select("shift", [""]).fetchall()[0]
            self.min_coverage_work_hours += min_value * shift_duration / 3600
            self.max_coverage_work_hours += max_value * shift_duration / 3600

        for person in self.db_adapter.select("person", ["id"]):
            person_id = person[0]
            for day in range(self.time_span):
                if not len(
                    self.db_adapter.cur.execute(
                        f"SELECT id FROM preallocation WHERE day={day} AND person_id={person_id} AND shift_id in ['OFF', 'HOL']"
                    )
                ).fetchall():
                    self.available_work_hours += 8

        self.total_work_hours = self.db_adapter.select_total_effective_hours()

        iso_day = datetime.date.fromisoformat(
            self.db_adapter.select("schedule", ["start_day"])[0]
        )
        if iso_day.weekday() in [5, 6]:
            self.weekend_days.append(0)
        for day_int in range(1, self.time_span):
            iso_day = iso_day + datetime.timedelta(days=day_int)
            if iso_day.weekday() in [5, 6]:
                self.weekend_days.append(day_int)

    def days_int(self, weekday):
        """
        return all days that match weekday
        :param weekday: 0 to 6 week day
        :return: List of day integers
        """
        days_int = []
        start_day_iso, time_span = datetime.date.fromisoformat(
            self.db_adapter.select("schedule", ["start_day", "time_span_days"])[0]
        )
        for day_int in range(time_span):
            iso_day = start_day_iso + datetime.timedelta(days=day_int)
            if iso_day.weekday() == weekday:
                days_int.append(day_int)

        return days_int


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
        for target, effective in self.db_adapter.select(
            "person", ["effective_hours", "target_hours"]
        ):
            deviations.append(target - effective)
            max_deviations.append(target)

        self.flaws = round(standard_deviation(deviations), 0)
        self.flaws_max = round(standard_deviation(max_deviations), 0)

        if self.flaws_max:
            self.score = round(100 - (100 * (1 - self.flaws / self.flaws_max)), 0)


@dataclasses.dataclass
class ExtraHours(FlawsAnalytic):
    """
    Estimate global extra hours
    """

    def compute(self):
        schedule_analytics = ScheduleAnalytics(self.db_adapter)
        schedule_analytics.compute()

        self.flaws_min = min(
            0,
            round(
                schedule_analytics.min_coverage_work_hours
                - schedule_analytics.available_work_hours
            ),
        )
        self.flaws = round(
            schedule_analytics.total_work_hours
            - schedule_analytics.min_coverage_work_hours
        )
        self.flaws_max = round(
            schedule_analytics.available_work_hours
            - schedule_analytics.min_coverage_work_hours
        )

        if self.flaws_max:
            self.score = round(100 - (100 * (1 - self.flaws / self.flaws_max)), 0)


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
            task_count = self.db_adapter.select_shift_tasks(self.shift, person=person)
            if task_count >= high_average:
                self.flaws += task_count - high_average
            else:
                self.flaws += low_average - task_count

        if self.flaws_max:
            self.score = round(100 - (100 * (1 - self.flaws / self.flaws_max)), 0)


@dataclasses.dataclass
class Sequences(FlawsAnalytic):
    """
    Estimate quality of sequences
    """

    def compute(self):
        schedule_analytics = ScheduleAnalytics(self.db_adapter)

        sequences = self.db_adapter.select(
            "sequence", ["id", "shift", "group", "order", "weekday"]
        )

        groups = set([sequence[1] for sequence in sequences])
        for group in groups:
            sequences = self.db_adapter.select(
                "sequence",
                ["id", "shift", "group", "order", "weekday"],
                f"group={group}",
                "order",
            )
            for sequence in sequences:
                sequence_id, shift, group, order, weekday = sequence
                days_int = schedule_analytics.days_int(sequence.day)
                self.flaws_max += len(days_int)
                match_days = self.db_adapter.select_shift_tasks(shift, days_int)
                self.flaws += len(days_int) - match_days

        if self.flaws_max:
            self.score = round(100 - (100 * (1 - self.flaws / self.flaws_max)), 0)


@dataclasses.dataclass
class WeekWorktime(FlawsAnalytic):
    """
    Estimate quality of week worktime
    """

    max_worktime_minutes: int = 50 * 3600  # 50 hours

    def compute(self):
        time_span = self.db_adapter.select("schedule", ["time_span_days"])[0]
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
                    person, days=[a for a in range(day, day + 7)]
                )
                duration = sum([duration for _, _, duration, _, _ in tasks])

                # add previous day task duration from midnight to end_time (if exists)
                previous_day_tasks = self.db_adapter.select_person_tasks(
                    person, days=[day - 1]
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
                    person, days=[day - 1]
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
            self.score = round(100 - (100 * (1 - self.flaws / self.flaws_max)), 0)


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
    weekdays: List[int] = dataclasses.field(default_factory=list)

    def compute(self):
        # if all shifts are attributed to people other than primary or secondary groups, then
        # max flaw count is equal to the max number of shift that can be attributed
        schedule_analytics = ScheduleAnalytics(self.db_adapter)
        days_int = schedule_analytics.days_int(self.weekdays)

        coverages = self.db_adapter.select(
            "coverage",
            ["max_value"],
            f"day IN {','.join(self.days)} AND shift_id='{self.shift}'",
        )
        self.flaws_max = 3 * sum([max_val for max_val in coverages])

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
        tasks = self.db_adapter.select_shift_tasks(shift_id=self.shift, days=day_int)
        for task in tasks:
            flaw = 0
            if task.person not in self.primary_people:
                flaw = 1
            elif task.person not in self.secondary_people:
                flaw = 3

            self.flaws += flaw

        if self.flaws_max:
            self.score = round(100 - (100 * (1 - self.flaws / self.flaws_max)), 0)
