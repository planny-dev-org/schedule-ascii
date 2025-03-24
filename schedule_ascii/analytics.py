import math


def standard_deviation(values):
    """
    Return standard deviation given a list of values

    :param values: list of tuples [(delta, target), ...]
    :return:
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
