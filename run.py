"""
Starting point of the application. This module is invoked from
the command line to run the analyses.
"""

import argparse
import sys

import config
from example_analysis import ExampleAnalysis
from label_resolution_analysis import LabelResolutionAnalysis
from contributor_activity_analysis import ContributorActivityAnalysis
from discussion_trend_analysis import DiscussionTrendAnalysis


def parse_args():
    """
    Parses the command line arguments that were provided along
    with the python command. The --feature flag must be provided as
    that determines what analysis to run. Optionally, you can pass in
    a user and/or a label to run analysis focusing on specific issues.

    You can also add more command line arguments following the pattern
    below.
    """
    ap = argparse.ArgumentParser("run.py")

    # Required parameter specifying what analysis to run
    ap.add_argument('--feature', '-f', type=int, required=True,
                    help='Which feature to run: 0 = example, 1 = label resolution, '
                         '2 = contributor activity, 3 = discussion trends')

    # Optional parameter for analyses focusing on a specific user (i.e., contributor)
    ap.add_argument('--user', '-u', type=str, required=False,
                    help='Optional parameter for analyses focusing on a specific user')

    # Optional parameter for analyses focusing on a specific label
    ap.add_argument('--label', '-l', type=str, required=False,
                    help='Optional parameter for analyses focusing on a specific label')

    return ap.parse_args()


def main():
    # Parse feature to call from command line arguments
    args = parse_args()
    # Add arguments to config so that they can be accessed in other parts of the application
    config.overwrite_from_args(args)

    # Run the feature specified in the --feature flag
    try:
        if args.feature == 0:
            ExampleAnalysis().run()
        elif args.feature == 1:
            LabelResolutionAnalysis().run()
        elif args.feature == 2:
            ContributorActivityAnalysis().run()
        elif args.feature == 3:
            DiscussionTrendAnalysis().run()
        else:
            print('Need to specify which feature to run with --feature flag (0, 1, 2, or 3).')
    except FileNotFoundError as err:
        print(f'\nERROR: {err}')
        sys.exit(1)


if __name__ == '__main__':
    main()
