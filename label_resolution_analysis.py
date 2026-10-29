"""
Feature 1: Label resolution analysis.

Question: Do different kinds of issues (identified by their labels) differ in
how long they take to close and in how much discussion they generate?

Run with:
    python run.py --feature 1                  (compare all labels)
    python run.py --feature 1 --label kind/bug (look at a single label)
"""

import difflib
from typing import List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config
from data_loader import DataLoader
from model import Issue

NO_LABEL = '(no label)'


class LabelResolutionAnalysis:
    """
    Compares labels by time to close, discussion intensity and number of
    distinct commenters. With --label, drills into one label and compares
    it to the project as a whole.
    """

    # Minimum number of resolved issues a label needs to be shown in the comparison
    MIN_RESOLVED = 5
    # Maximum number of labels shown in the comparison chart
    TOP_N = 12

    def __init__(self):
        """
        Constructor
        """
        # Parameter is passed in via command line (--label)
        label = config.get_parameter('label')
        self.LABEL: Optional[str] = str(label).strip() if label is not None else None

    def run(self):
        """
        Starting point for this analysis.
        """
        issues: List[Issue] = DataLoader().get_issues()

        print('\n' + '=' * 70)
        print('QUESTION: Do issue labels differ in time to close and in discussion?')
        print('METHOD:   Per issue we compute days from creation to the closing event,')
        print('          the number of human comments and the number of distinct')
        print('          commenters (bots excluded). Issues are then grouped by label.')
        print('          Closed issues without a closing event are left out of the')
        print('          time statistics (they cannot be timed).')
        print('=' * 70)

        table = self._issue_table(issues)
        if table.empty:
            print('\nNo issues available to analyze.')
            return

        if self.LABEL:
            self._run_single_label(table)
        else:
            self._run_all_labels(table)

    # ------------------------------------------------------------------ data

    def _issue_table(self, issues: List[Issue]) -> pd.DataFrame:
        """
        One row per issue with the measures needed by this analysis.
        """
        rows = []
        for issue in issues:
            comments = issue.human_comments()
            rows.append({
                'number': issue.number,
                'labels': list(issue.labels) if issue.labels else [NO_LABEL],
                'closed': issue.state is not None and issue.state.value == 'closed',
                'days_to_close': issue.days_to_close(),
                'comments': len(comments),
                'commenters': len({c.author for c in comments}),
                'commenter_names': [c.author for c in comments],
            })
        return pd.DataFrame(rows)

    def _summarize_by_label(self, table: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregates the issue table per label.
        """
        exploded = table.explode('labels')
        grouped = exploded.groupby('labels')
        summary = pd.DataFrame({
            'issues': grouped.size(),
            'resolved': grouped['days_to_close'].count(),
            'median_days': grouped['days_to_close'].median(),
            'mean_comments': grouped['comments'].mean(),
            'mean_commenters': grouped['commenters'].mean(),
        })
        return summary

    # ------------------------------------------------------- all labels mode

    def _run_all_labels(self, table: pd.DataFrame):
        summary = self._summarize_by_label(table)
        summary = summary.drop(index=NO_LABEL, errors='ignore')  # not a real label
        ranked = summary[summary['resolved'] >= self.MIN_RESOLVED]
        ranked = ranked.sort_values('issues', ascending=False).head(self.TOP_N)
        ranked = ranked.sort_values('median_days')

        if ranked.empty:
            print(f'\nNo label has at least {self.MIN_RESOLVED} resolved issues.')
            return

        unresolved = int(table['closed'].sum() - table['days_to_close'].count())
        print(f'\n{len(table)} issues, {int(table["days_to_close"].count())} with a measurable '
              f'time to close ({unresolved} closed issues have no closing event).')
        print(f'Showing the {len(ranked)} most common labels with >= {self.MIN_RESOLVED} resolved issues:\n')
        view = ranked.rename(columns={
            'issues': 'issues', 'resolved': 'resolved', 'median_days': 'median days to close',
            'mean_comments': 'comments/issue', 'mean_commenters': 'commenters/issue'})
        print(view.round(2).to_string())

        fastest, slowest = ranked.index[0], ranked.index[-1]
        print('\nFINDING:')
        print(f'  "{fastest}" issues close fastest (median {ranked.loc[fastest, "median_days"]:.1f} days), '
              f'while "{slowest}" issues are slowest (median {ranked.loc[slowest, "median_days"]:.1f} days).')
        if len(ranked) >= 4:
            corr = ranked['median_days'].rank().corr(ranked['mean_comments'].rank())
            if pd.notna(corr):
                direction = 'tend to take longer to close' if corr > 0.3 else (
                    'tend to close faster' if corr < -0.3 else 'show no clear relationship with closing speed')
                print(f'  Across these labels, issues with more discussion {direction} '
                      f'(rank correlation {corr:+.2f}, n={len(ranked)} labels).')
        print('  Note: medians for labels with few issues are less reliable.\n')

        self._plot_comparison(ranked)

    def _plot_comparison(self, ranked: pd.DataFrame):
        """
        Two bar charts sharing the same label order: median days to close and
        discussion per issue.
        """
        labels = list(ranked.index)
        y = np.arange(len(labels))
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 7), sharey=True)

        ax1.barh(y, ranked['median_days'], color='#4c72b0', label='Median days to close')
        ax1.set_yticks(y)
        ax1.set_yticklabels(labels)
        ax1.set_title('Median time to close by label')
        ax1.set_xlabel('Median days from creation to close')
        ax1.set_ylabel('Label')
        ax1.legend(loc='lower right')
        for yi, v in zip(y, ranked['median_days']):
            ax1.text(v, yi, f' {v:.1f}', va='center', fontsize=8)

        ax2.barh(y - 0.2, ranked['mean_comments'], height=0.4, color='#dd8452',
                 label='Comments per issue')
        ax2.barh(y + 0.2, ranked['mean_commenters'], height=0.4, color='#55a868',
                 label='Distinct commenters per issue')
        ax2.set_title('Discussion per issue by label')
        ax2.set_xlabel('Average per issue (bots excluded)')
        ax2.legend(loc='upper center', bbox_to_anchor=(0.5, -0.1), ncol=2)

        fig.suptitle(f'Issue labels: resolution time and discussion (top {len(labels)} labels)')
        plt.tight_layout()
        plt.show()

    # ------------------------------------------------------ single label mode

    def _find_label(self, table: pd.DataFrame) -> Optional[str]:
        """
        Case-insensitive exact match of the requested label. If there is no
        match, suggests similar labels and returns None.
        """
        all_labels = sorted({l for labels in table['labels'] for l in labels})
        wanted = self.LABEL.lower()
        for label in all_labels:
            if label.lower() == wanted:
                return label

        similar = [l for l in all_labels if wanted in l.lower() or l.lower() in wanted]
        for match in difflib.get_close_matches(wanted, [l.lower() for l in all_labels], n=5, cutoff=0.6):
            original = next(l for l in all_labels if l.lower() == match)
            if original not in similar:
                similar.append(original)
        print(f'\nLabel "{self.LABEL}" was not found.')
        if similar:
            print('Did you mean one of these? ' + ', '.join(similar[:10]))
        else:
            counts = table.explode('labels')['labels'].value_counts().head(10)
            print('Most common labels: ' + ', '.join(counts.index))
        return None

    def _run_single_label(self, table: pd.DataFrame):
        label = self._find_label(table)
        if label is None:
            return

        subset = table[table['labels'].apply(lambda ls: label in ls)]
        days = subset['days_to_close'].dropna()
        all_days = table['days_to_close'].dropna()
        commenters = pd.Series([n for names in subset['commenter_names'] for n in names])

        print(f'\nLabel: {label}')
        print(f'  Issues with this label:      {len(subset)} '
              f'({int(subset["closed"].sum())} closed, {len(subset) - int(subset["closed"].sum())} open)')
        print(f'  Closed with timing data:     {len(days)}')
        if len(days):
            print(f'  Days to close (median/mean/90th pct): '
                  f'{days.median():.1f} / {days.mean():.1f} / {days.quantile(0.9):.1f}')
        print(f'  Comments per issue:          {subset["comments"].mean():.2f} '
              f'(all issues: {table["comments"].mean():.2f})')
        print(f'  Distinct commenters / issue: {subset["commenters"].mean():.2f} '
              f'(all issues: {table["commenters"].mean():.2f})')
        if not commenters.empty:
            top = commenters.value_counts().head(5)
            print('  Most active commenters:      ' + ', '.join(f'{n} ({c})' for n, c in top.items()))

        print('\nFINDING:')
        if len(days) == 0:
            print(f'  No issue labelled "{label}" has a measurable time to close, '
                  'so no resolution comparison is possible.')
            return
        ratio = days.median() / all_days.median() if all_days.median() > 0 else float('nan')
        print(f'  Issues labelled "{label}" close in a median of {days.median():.1f} days, versus '
              f'{all_days.median():.1f} days for all issues'
              + (f' ({ratio:.1f}x).' if pd.notna(ratio) else '.'))
        if len(days) < self.MIN_RESOLVED:
            print(f'  Caution: only {len(days)} resolved issue(s), so this is a weak estimate.')
        print()

        self._plot_label_distribution(label, days, all_days)

    def _plot_label_distribution(self, label: str, days: pd.Series, all_days: pd.Series):
        """
        Histogram (log-spaced bins) of days to close for the label, with the
        median of the label and of all issues marked.
        """
        upper = max(days.max(), all_days.max(), 1)
        bins = np.logspace(np.log10(0.01), np.log10(upper * 1.1), 25)
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.hist(days.clip(lower=0.01), bins=bins, color='#4c72b0', alpha=0.85,
                label=f'Issues labelled {label} (n={len(days)})')
        ax.axvline(days.median(), color='#c44e52', linestyle='--', linewidth=2,
                   label=f'Median for {label}: {days.median():.1f} days')
        ax.axvline(all_days.median(), color='#222222', linestyle=':', linewidth=2,
                   label=f'Median for all issues: {all_days.median():.1f} days')
        ax.set_xscale('log')
        ax.set_title(f'Time to close for issues labelled "{label}"')
        ax.set_xlabel('Days from creation to close (log scale)')
        ax.set_ylabel('Number of issues')
        ax.legend()
        plt.tight_layout()
        plt.show()


if __name__ == '__main__':
    # Invoke run method when running this module directly
    LabelResolutionAnalysis().run()
