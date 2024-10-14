import math


def standard_deviation(values):
    """
    Return standard deviation given a list of values
    :param values:
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

    return math.sqrt(std_deviation_term / values_size)
