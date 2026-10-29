"""
Feature 2: Contributor activity analysis.

Question: Who does the work on the project, and do the contributors who
comment a lot also take part in triage by labelling or closing issues?

Run with:
    python run.py --feature 2                (project-wide view)
    python run.py --feature 2 --user dimbleby (one contributor vs. the top ones)
"""

import difflib
from typing import List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config
from data_loader import DataLoader
from model import Issue

# Event types counted for each activity measure
COMMENT_EVENTS = {'commented'}
LABEL_EVENTS = {'labeled', 'unlabeled'}
CLOSE_EVENTS = {'closed'}


class ContributorActivityAnalysis:
    """
    Counts comments, label actions and closes per contributor (bots excluded)
    and relates the three measures to each other.
    """

    # Number of contributors shown in the bar chart
    TOP_N = 10
    # A contributor with at least this many comments counts as a "frequent commenter"
    FREQUENT_COMMENTS = 10
    # Minimum total events for a contributor to be included in the correlation
    MIN_ACTIVE_EVENTS = 5

    def __init__(self):
        """
        Constructor
        """
        # Parameter is passed in via command line (--user)
        user = config.get_parameter('user')
        self.USER: Optional[str] = str(user).strip() if user is not None else None

    def run(self):
        """
        Starting point for this analysis.
        """
        issues: List[Issue] = DataLoader().get_issues()

        print('\n' + '=' * 70)
        print('QUESTION: Who does the work on the project, and do frequent commenters')
        print('          also label or close issues?')
        print('METHOD:   Every event is classified as a comment, a label action')
        print('          (labeled/unlabeled) or a close. Labels and closes by the issue')
        print('          reporter on their own issue are not counted as triage (many')
        print('          labels are auto-applied by issue templates). Counts are')
        print('          aggregated per contributor; bots and unknown users are excluded.')
        print('          Spearman rank correlations relate the measures.')
        print('=' * 70)

        activity = self._aggregate(issues)
        if activity.empty:
            print('\nNo contributor activity found.')
            return

        if self.USER:
            if not self._print_user_summary(activity):
                return
        else:
            self._print_summary(activity)
            self._print_correlations(activity)
            self._print_finding(activity)

        self._plot_activity(activity)
        if not self.USER and len(activity) >= 2:
            self._plot_relationship(activity)

    # ------------------------------------------------------------------ data

    def _aggregate(self, issues: List[Issue]) -> pd.DataFrame:
        """
        Classifies events and aggregates counts per contributor.
        """
        records = []
        for issue in issues:
            for event in issue.events:
                if not event.is_human:
                    continue
                if event.event_type in COMMENT_EVENTS:
                    kind = 'comments'
                elif event.event_type in LABEL_EVENTS:
                    if event.author == issue.creator:
                        continue  # labels applied by the reporter (e.g. via issue templates) are not triage
                    kind = 'label_actions'
                elif event.event_type in CLOSE_EVENTS:
                    if event.author == issue.creator:
                        continue  # closing your own issue is not triage work
                    kind = 'closes'
                else:
                    continue
                records.append({'author': event.author, 'kind': kind, 'issue': issue.number})

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        counts = df.pivot_table(index='author', columns='kind', values='issue',
                                aggfunc='count', fill_value=0)
        for column in ('comments', 'label_actions', 'closes'):
            if column not in counts:
                counts[column] = 0
        counts.columns.name = None
        counts.index.name = 'contributor'
        counts['issues_touched'] = df.groupby('author')['issue'].nunique()
        counts['triage_actions'] = counts['label_actions'] + counts['closes']
        counts['total'] = counts['comments'] + counts['triage_actions']
        return counts.sort_values('total', ascending=False)

    # ---------------------------------------------------------------- output

    def _print_summary(self, activity: pd.DataFrame):
        commenters = activity[activity['comments'] > 0]
        also_triage = commenters[commenters['triage_actions'] > 0]
        frequent = activity[activity['comments'] >= self.FREQUENT_COMMENTS]
        frequent_triage = frequent[frequent['triage_actions'] > 0]
        others = commenters[commenters['comments'] < self.FREQUENT_COMMENTS]
        others_triage = others[others['triage_actions'] > 0]

        print(f'\n{len(activity)} human contributors with activity; '
              f'{len(commenters)} commented, {len(also_triage)} of those also labeled or closed issues.\n')
        print(f'Top {self.TOP_N} contributors by total activity:\n')
        view = activity.head(self.TOP_N)[['comments', 'label_actions', 'closes', 'issues_touched']]
        print(view.to_string())

    def _print_correlations(self, activity: pd.DataFrame):
        active = activity[activity['total'] >= self.MIN_ACTIVE_EVENTS]
        if len(active) < 2:
            print('\nNot enough active contributors to calculate correlations.')
            return
        print(f'\nSpearman rank correlation between activity measures '
              f'(contributors with >= {self.MIN_ACTIVE_EVENTS} events, n={len(active)}):')
        pairs = [('comments', 'label_actions'), ('comments', 'closes'), ('comments', 'triage_actions')]
        for a, b in pairs:
            corr = active[a].rank().corr(active[b].rank())
            print(f'  {a:>14} vs {b:<14} {corr:+.2f}' if pd.notna(corr)
                  else f'  {a:>14} vs {b:<14} n/a')
        print('  (+1 = people who do more of one also do more of the other, 0 = unrelated)')

    def _print_finding(self, activity: pd.DataFrame):
        commenters = activity[activity['comments'] > 0]
        frequent = commenters[commenters['comments'] >= self.FREQUENT_COMMENTS]
        others = commenters[commenters['comments'] < self.FREQUENT_COMMENTS]
        share = lambda df: (100 * (df['triage_actions'] > 0).sum() / len(df)) if len(df) else float('nan')

        print('\nFINDING:')
        if len(frequent) and len(others):
            print(f'  {share(frequent):.1f}% of frequent commenters (>= {self.FREQUENT_COMMENTS} comments, '
                  f'n={len(frequent)}) also label or close issues, compared with '
                  f'{share(others):.1f}% of occasional commenters (n={len(others)}).')
        active = activity[activity['total'] >= self.MIN_ACTIVE_EVENTS]
        if len(active) >= 2:
            corr = active['comments'].rank().corr(active['triage_actions'].rank())
            if pd.notna(corr):
                meaning = ('people who comment more also triage more' if corr > 0.3 else
                           'people who comment more tend to triage less' if corr < -0.3 else
                           'commenting volume and triage work are only weakly related')
                print(f'  Among active contributors, {meaning} (rank correlation {corr:+.2f}).')
        top = activity.head(self.TOP_N)
        print(f'  The top {self.TOP_N} contributors account for '
              f'{100 * top["total"].sum() / activity["total"].sum():.0f}% of all counted activity.\n')

    def _print_user_summary(self, activity: pd.DataFrame) -> bool:
        """
        Prints the breakdown for the requested contributor. Returns False if
        the user does not exist in the data.
        """
        lookup = {name.lower(): name for name in activity.index}
        name = lookup.get(self.USER.lower())
        if name is None:
            print(f'\nNo activity found for user "{self.USER}" (bots are excluded).')
            close = difflib.get_close_matches(self.USER.lower(), list(lookup), n=5, cutoff=0.5)
            if close:
                print('Did you mean: ' + ', '.join(lookup[c] for c in close) + '?')
            else:
                print('Most active contributors: ' + ', '.join(activity.head(5).index))
            return False

        self.USER = name  # use the exact spelling from the data
        row = activity.loc[name]
        rank = int(activity['total'].rank(ascending=False, method='min')[name])
        share = 100 * row['total'] / activity['total'].sum()
        print(f'\nContributor: {name}')
        print(f'  Comments:        {int(row["comments"])}')
        print(f'  Label actions:   {int(row["label_actions"])}')
        print(f'  Issues closed:   {int(row["closes"])}')
        print(f'  Issues touched:  {int(row["issues_touched"])}')
        print(f'  Overall rank:    #{rank} of {len(activity)} contributors ({share:.1f}% of all activity)')

        top = activity.head(self.TOP_N)
        print('\nFINDING:')
        triage_share = 100 * row['triage_actions'] / row['total'] if row['total'] else 0
        print(f'  {triage_share:.0f}% of {name}\'s activity is triage (labeling/closing) versus '
              f'{100 * top["triage_actions"].sum() / top["total"].sum():.0f}% for the top {self.TOP_N} contributors overall.\n')
        return True

    # ---------------------------------------------------------------- charts

    def _plot_activity(self, activity: pd.DataFrame):
        """
        Grouped bar chart of comments, label actions and closes. Without a
        user: the top contributors. With a user: that user next to the average
        of the top contributors.
        """
        measures = [('comments', 'Comments', '#4c72b0'),
                    ('label_actions', 'Label actions', '#dd8452'),
                    ('closes', 'Issues closed', '#55a868')]
        top = activity.head(self.TOP_N)
        if self.USER:
            data = pd.DataFrame([activity.loc[self.USER], top.mean()],
                                index=[self.USER, f'Average of top {self.TOP_N}'])
            title = f'Activity of {self.USER} compared with the top {self.TOP_N} contributors'
        else:
            data = top
            title = f'Activity of the top {self.TOP_N} contributors (bots excluded)'

        x = np.arange(len(data))
        width = 0.27
        fig, ax = plt.subplots(figsize=(12, 6))
        for i, (column, label, color) in enumerate(measures):
            ax.bar(x + (i - 1) * width, data[column], width, label=label, color=color)
        ax.set_xticks(x)
        ax.set_xticklabels(data.index, rotation=30, ha='right')
        ax.set_title(title)
        ax.set_xlabel('Contributor')
        ax.set_ylabel('Number of events')
        ax.legend()
        plt.tight_layout()
        plt.show()

    def _plot_relationship(self, activity: pd.DataFrame):
        """
        Scatter plot of comments versus triage actions per contributor.
        """
        data = activity[activity['total'] > 0]
        triagers = data[data['triage_actions'] > 0]
        comment_only = data[data['triage_actions'] == 0]

        fig, ax = plt.subplots(figsize=(10, 7))
        ax.scatter(comment_only['comments'], comment_only['triage_actions'], s=25,
                   color='#8c8c8c', alpha=0.6, label=f'Comments only ({len(comment_only)})')
        ax.scatter(triagers['comments'], triagers['triage_actions'], s=40,
                   color='#c44e52', alpha=0.8, label=f'Also label/close issues ({len(triagers)})')
        for i, (name, row) in enumerate(data.head(6).iterrows()):
            ax.annotate(name, (row['comments'], row['triage_actions']), fontsize=8,
                        xytext=(5, 5 if i % 2 == 0 else -12), textcoords='offset points')
        ax.set_xscale('symlog', linthresh=1)
        ax.set_yscale('symlog', linthresh=1)
        ax.set_title('Do frequent commenters also triage issues?')
        ax.set_xlabel('Comments written (symlog scale)')
        ax.set_ylabel('Label actions + closes (symlog scale)')
        ax.legend()
        plt.tight_layout()
        plt.show()


if __name__ == '__main__':
    # Invoke run method when running this module directly
    ContributorActivityAnalysis().run()
