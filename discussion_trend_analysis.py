"""
Feature 3: Discussion trend analysis (project-level).

Question: How has issue activity on the project changed over time, and has
the time until someone responds to a new issue changed with it?

Run with:
    python run.py --feature 3
"""

from datetime import timezone
from typing import List, Optional

import matplotlib.pyplot as plt
import pandas as pd

from data_loader import DataLoader
from model import Issue, _as_utc


class DiscussionTrendAnalysis:
    """
    Buckets issues and events by quarter and tracks how many issues are
    opened and closed, how much discussion happens and how quickly new
    issues get a first response.
    """

    # A quarter needs at least this many new issues to report a median response time
    MIN_ISSUES_PER_QUARTER = 3
    # A year needs at least this many new issues to be used in the first-vs-last comparison
    MIN_ISSUES_PER_YEAR = 10

    def __init__(self):
        """
        Constructor
        """
        # Issue-level first-response times (filled by _quarterly_metrics)
        self._response = pd.DataFrame(columns=['quarter', 'hours'])

    def run(self):
        """
        Starting point for this analysis.
        """
        issues: List[Issue] = DataLoader().get_issues()

        print('\n' + '=' * 70)
        print('QUESTION: How has issue activity changed over time, and how quickly do')
        print('          new issues get a first response?')
        print('METHOD:   Issues and events are bucketed by calendar quarter: issues')
        print('          opened (creation date), issues closed (date of the closing event), human')
        print('          comments, and the median hours until someone other than the')
        print('          creator first comments (bots excluded).')
        print('=' * 70)

        metrics = self._quarterly_metrics(issues)
        if metrics is None:
            print('\nNo dated issues available to analyze.')
            return

        self._print_summary(metrics)
        self._plot_trends(metrics)

    # ------------------------------------------------------------------ data

    @staticmethod
    def _quarter(value) -> Optional[pd.Period]:
        """
        Converts a datetime to its calendar quarter (UTC), or None.
        """
        if value is None:
            return None
        utc = _as_utc(value).astimezone(timezone.utc).replace(tzinfo=None)
        return pd.Timestamp(utc).to_period('Q')

    @staticmethod
    def _first_response_hours(issue: Issue) -> Optional[float]:
        """
        Hours from issue creation to the first comment by a human who is not
        the issue creator. None if nobody else has commented.
        """
        if issue.created_date is None:
            return None
        times = [_as_utc(c.event_date) for c in issue.human_comments()
                 if c.author != issue.creator and c.event_date is not None]
        if not times:
            return None
        hours = (min(times) - _as_utc(issue.created_date)).total_seconds() / 3600
        return hours if hours >= 0 else None

    def _quarterly_metrics(self, issues: List[Issue]) -> Optional[pd.DataFrame]:
        opened, closed, comments, response = [], [], [], []
        for issue in issues:
            created_q = self._quarter(issue.created_date)
            if created_q is None:
                continue
            opened.append(created_q)
            hours = self._first_response_hours(issue)
            if hours is not None:
                response.append({'quarter': created_q, 'hours': hours})
            closed_q = self._quarter(issue.closed_date)
            if closed_q is not None:
                closed.append(closed_q)
            comments.extend(self._quarter(c.event_date) for c in issue.human_comments()
                            if c.event_date is not None)

        if not opened:
            return None

        index = pd.period_range(min(opened), max(opened + closed), freq='Q')
        metrics = pd.DataFrame(index=index)
        metrics['opened'] = pd.Series(opened).value_counts().reindex(index, fill_value=0)
        metrics['closed'] = pd.Series(closed, dtype='object').value_counts().reindex(index, fill_value=0) \
            if closed else 0
        metrics['comments'] = pd.Series(comments, dtype='object').value_counts().reindex(index, fill_value=0) \
            if comments else 0

        resp = pd.DataFrame(response)
        self._response = resp
        if resp.empty:
            metrics['median_response_hours'] = float('nan')
        else:
            grouped = resp.groupby('quarter')['hours']
            median = grouped.median().where(grouped.size() >= self.MIN_ISSUES_PER_QUARTER)
            metrics['median_response_hours'] = median.reindex(index)
        return metrics

    # ---------------------------------------------------------------- output

    def _print_summary(self, metrics: pd.DataFrame):
        first, last = metrics.index[0], metrics.index[-1]
        print(f'\nCovering {first} to {last} '
              f'({int(metrics["opened"].sum())} issues opened, {int(metrics["closed"].sum())} closed, '
              f'{int(metrics["comments"].sum())} human comments).')
        print(f'Note: {last} may be incomplete if the data was exported part-way through it.\n')

        yearly = metrics.groupby(metrics.index.year).agg(
            opened=('opened', 'sum'), closed=('closed', 'sum'), comments=('comments', 'sum'))
        yearly['comments_per_opened_issue'] = (yearly['comments'] / yearly['opened'].where(yearly['opened'] > 0)).round(2)
        if not self._response.empty:
            by_year = self._response.assign(year=self._response['quarter'].apply(lambda q: q.year)).groupby('year')['hours']
            yearly['median_first_response_hours'] = by_year.median().where(by_year.size() >= self.MIN_ISSUES_PER_YEAR).round(1)
        else:
            yearly['median_first_response_hours'] = float('nan')
        print(yearly.to_string())

        print('\nFINDING:')
        peak = metrics['opened'].idxmax()
        print(f'  Issue creation peaked in {peak} with {int(metrics.loc[peak, "opened"])} new issues.')
        total_open, total_closed = metrics['opened'].sum(), metrics['closed'].sum()
        print(f'  Overall, {int(total_closed)} issues were closed versus {int(total_open)} opened '
              f'(closed/opened = {total_closed / total_open:.2f}).')

        eligible = yearly[(yearly['opened'] >= self.MIN_ISSUES_PER_YEAR) & yearly['median_first_response_hours'].notna()]
        if len(eligible) >= 2:
            y0, y1 = eligible.index[0], eligible.index[-1]
            h0 = eligible.loc[y0, 'median_first_response_hours']
            h1 = eligible.loc[y1, 'median_first_response_hours']
            change = 'faster' if h1 < h0 else 'slower'
            print(f'  Median first response went from {h0:.1f} h in {y0} to {h1:.1f} h in {y1} ({change}).')
        else:
            print('  Not enough data per year to compare first-response times over time.')
        print()

    # ---------------------------------------------------------------- charts

    def _plot_trends(self, metrics: pd.DataFrame):
        """
        Three stacked charts sharing the quarter axis.
        """
        labels = [str(p) for p in metrics.index]
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(13, 10), sharex=True)

        ax1.plot(labels, metrics['opened'], marker='o', color='#4c72b0', label='Issues opened')
        ax1.plot(labels, metrics['closed'], marker='s', color='#dd8452', label='Issues closed')
        ax1.set_title('Issues opened and closed per quarter')
        ax1.set_ylabel('Number of issues')
        ax1.legend()

        ax2.plot(labels, metrics['comments'], marker='o', color='#55a868', label='Human comments')
        ax2.set_title('Discussion volume per quarter')
        ax2.set_ylabel('Number of comments')
        ax2.legend()

        ax3.plot(labels, metrics['median_response_hours'], marker='o', color='#c44e52',
                 label=f'Median hours to first response (quarters with >= {self.MIN_ISSUES_PER_QUARTER} issues)')
        ax3.set_title('Time to first response by quarter the issue was opened')
        ax3.set_yscale('log')
        ax3.set_ylabel('Median hours (log scale)')
        ax3.set_xlabel('Quarter')
        ax3.legend()

        step = max(1, len(labels) // 14)
        ax3.set_xticks(range(0, len(labels), step))
        ax3.set_xticklabels(labels[::step], rotation=45, ha='right')
        fig.suptitle('Poetry issue activity over time')
        plt.tight_layout()
        plt.show()


if __name__ == '__main__':
    # Invoke run method when running this module directly
    DiscussionTrendAnalysis().run()
