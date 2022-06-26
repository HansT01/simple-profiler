from functools import wraps
import inspect
from time import perf_counter
from typing import Any, Dict, Callable, List, Tuple
from matplotlib import pyplot as plt
import numpy as np
import numpy.typing as npt
from tabulate import tabulate
from operator import itemgetter


class TimeProfiler:
    """TimeProfiler is a class for quickly storing the time taken for each method to complete, and displaying it as an easy-to-read table."""

    profiles: Dict[Callable, List[Tuple[float, float]]] = {}
    profiles_arr: Dict[Callable, npt.NDArray] = None

    ORDER_BY_NAME = 0
    ORDER_BY_CALLS = 1
    ORDER_BY_AVERAGE = 2
    ORDER_BY_LONGEST = 3
    ORDER_BY_BOTTLENECK = 4

    @staticmethod
    def reset():
        """Resets all profiles."""
        TimeProfiler.profiles = {}

    @staticmethod
    def profile_method(f):
        """Method decorator that adds the decorated method to the list of time profiles."""

        @wraps(f)
        def wrapper(*args, **kwargs):
            profiles = TimeProfiler.profiles
            if f not in profiles:
                profiles[f] = []

            # List used over tuples to guarantee call order
            pair = [None, None]
            profiles[f] += [pair]

            pair[0] = perf_counter()
            result = f(*args, **kwargs)
            pair[1] = perf_counter()
            return result

        return wrapper

    @staticmethod
    def profile_class_methods(cls):
        """Class decorator for adding profile_method to all contained methods within the class."""

        # https://stackoverflow.com/a/57368193
        for name, method in inspect.getmembers(cls):
            if (not inspect.ismethod(method) and not inspect.isfunction(method)) or inspect.isbuiltin(method):
                continue
            setattr(cls, name, TimeProfiler.profile_method(method))
        return cls

    @staticmethod
    def display_profiles(order_by=0, reverse=False, full_name=False):
        """Prints out all profiles to console as a table, ordered by the order_by parameter.

        Args:
            order_by (int, optional): Optional ordering using provided ORDER_BY_ fields. Defaults to ORDER_BY_NAME.
            reverse (bool, optional): Reverse row order? Defaults to False.
            full_name (bool, optional): Display full name of methods? Defaults to False.
        """
        TimeProfiler.__create_arr_profiles()
        profiles_arr = TimeProfiler.profiles_arr
        table = []
        for key in profiles_arr:
            arr_profile = profiles_arr[key]
            n = len(arr_profile)

            elapsed_arr = arr_profile[1] - arr_profile[0]
            sum = np.sum(elapsed_arr)
            longest = elapsed_arr.max()

            avg = sum / n
            bottleneck = TimeProfiler.__calculate_bottleneck(arr_profile)

            row = [
                key.__qualname__ if full_name else key.__name__,
                n,
                round(avg * 1000, 2),
                round(longest * 1000, 2),
                round(bottleneck * 1000, 2),
            ]

            table += [row]

        table.sort(key=itemgetter(order_by), reverse=reverse)

        print(
            tabulate(
                table,
                headers=[
                    "Name",
                    "Calls",
                    "Average (ms)",
                    "Longest (ms)",
                    "Bottleneck (ms)",
                ],
                floatfmt=",.2f",
            )
        )

    @staticmethod
    def plot_profiles(reverse=False, **kwargs):
        """Plots the profiles as a range bar chart, ordered by first call.

        Args:
            reverse (bool, optional): Reverse order? Defaults to False.
            **kwargs: ~matplotlib.patches.Polygon properties
        """
        TimeProfiler.__create_arr_profiles()
        earliest, latest = TimeProfiler.__get_time_range()
        new_profiles = TimeProfiler.__squash_profiles(earliest, latest)

        # Sort by first 'start' time
        sorted_profiles = dict(sorted(new_profiles.items(), key=lambda item: item[1], reverse=reverse))
        TimeProfiler.__plot_data(sorted_profiles, 0, latest - earliest, **kwargs)

    @staticmethod
    def __create_arr_profiles():
        profiles = TimeProfiler.profiles
        profiles_arr = {}
        for key in profiles:
            profile = profiles[key]
            n = len(profile)
            profiles_arr[key] = np.array([[profile[j][i] for j in range(0, n)] for i in [0, 1]])
        TimeProfiler.profiles_arr = profiles_arr

    @staticmethod
    def __get_time_range() -> Tuple[float, float]:
        """Returns the time range across all profiles.

        Returns:
            Tuple[float, float]: earliest time (s), latest time (s)
        """
        profiles_arr = TimeProfiler.profiles_arr
        earliest = min([profiles_arr[key].min() for key in profiles_arr])
        latest = max([profiles_arr[key].max() for key in profiles_arr])
        return earliest, latest

    @staticmethod
    def __squash_profiles(earliest: float, latest: float):
        """Prepares the profiles to be read by __plot_data.

        Args:
            earliest (float): Starting time
            latest (float): Ending time

        Returns:
            Dict[Callable, List[Tuple[float, float]]]: Data object
        """

        profiles_arr = TimeProfiler.profiles_arr
        new_profiles: Dict[Callable, List[Tuple[float, float]]] = {}
        time_frame = latest - earliest

        # Fill in new_profiles with normalized times
        for key in profiles_arr:
            arr_profile: npt.NDArray = profiles_arr[key]
            n = arr_profile.shape[1]

            new_starts = (arr_profile[0] - earliest) / time_frame
            new_ends = (arr_profile[1] - earliest) / time_frame

            new_profiles[key] = [(new_starts[i], new_ends[i]) for i in range(0, n)]

        return new_profiles

    @staticmethod
    def __calculate_bottleneck(profile: npt.NDArray) -> float:
        n = profile.shape[1]

        starts = np.sort(profile[0])
        ends = np.sort(profile[1])

        bottleneck = 0
        j = 0
        for i in range(0, n):
            if i == n - 1 or starts[i + 1] > ends[i]:
                bottleneck += ends[i] - starts[j]
                j = i + 1
        return bottleneck

    @staticmethod
    def __plot_data(
        data: Dict[Callable, List[Tuple[float, float]]],
        xmin: float,
        xmax: float,
        full_name=False,
        alpha=0.4,
        fc="#000",
        ec="#000",
        **kwargs
    ):
        """Plots the data using the matplotlib library.

        Args:
            data (Dict[Callable, List[Tuple[float, float]]]): Data object
            xmin (float): lower x limit
            xmax (float): upper x limit
            full_name (bool, optional): Display full name of methods? Defaults to False.
            **kwargs: ~matplotlib.patches.Polygon properties
        """
        fig, ax = plt.subplots()
        width = 1

        ax.set_xlim(xmin, xmax)

        for i, pair in enumerate(data.items()):
            for value in pair[1]:
                x0, x1 = value
                ax.axhspan(
                    ymin=i - width / 2,
                    ymax=i + width / 2,
                    xmin=x0,
                    xmax=x1,
                    alpha=alpha,
                    fc=fc,
                    ec=ec,
                    **kwargs,
                )

        ax.set_yticks(np.arange(0, len(data)))
        ax.set_yticklabels([key.__qualname__ if full_name else key.__name__ for key in data.keys()])

        ax.set_title("Time profile ranges")
        ax.set_xlabel("Time elapsed (s)")

        plt.tight_layout()
        plt.show()


def use_profiler(instance: Any):
    if inspect.ismethod(instance) or inspect.isfunction(instance):
        return TimeProfiler.profile_method(instance)
    else:
        try:
            return TimeProfiler.profile_class_methods(instance)
        except:
            print("Could not identify instance")
            return instance


if __name__ == "__main__":
    from random import randint
    from time import sleep
    import concurrent.futures

    @use_profiler
    class ExampleClass:
        def method_a(self, num):
            with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
                # Run method b as threads
                fs = (executor.submit(self.method_b) for _ in range(0, num))

                # Wait for all futures to complete
                for f in concurrent.futures.as_completed(fs):
                    pass

            self.method_d()

        def method_b(self):
            sleep(randint(0, 10000) / 10000)
            self.method_c()

        def method_c(self):
            sleep(randint(0, 10000) / 10000)

        def method_d(self):
            sleep(randint(0, 10000) / 10000)

        @staticmethod
        def method_e():
            sleep(randint(0, 10000) / 10000)

    example1 = ExampleClass()
    example1.method_a(5)

    TimeProfiler.display_profiles(TimeProfiler.ORDER_BY_NAME)
    TimeProfiler.plot_profiles()
