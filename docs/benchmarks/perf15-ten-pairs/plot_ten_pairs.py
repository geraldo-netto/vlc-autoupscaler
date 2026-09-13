"""Export paired-run variation without pooling frames into fake repetitions."""
import argparse
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

CLIPS = ('animation', 'motion', 'live-action-540')
COLORS = {'local': '#1764a0', 'latency': '#c65f0c', 'duplicate': '#555555'}


def limits(rows, metric):
    values = [100*(value-1) for row in rows for value in row['metrics'][metric]['individual_ratios']]
    return math.floor((min(values)-5)/10)*10, math.ceil((max(values)+5)/10)*10


def draw_group(axis, row, metric):
    treatment = row['treatment']
    x = [value+1 for value in row['repeats']]
    y = [100*(value-1) for value in row['metrics'][metric]['individual_ratios']]
    color = COLORS[treatment]
    if treatment == 'duplicate':
        axis.scatter(x, y, marker='x', color=color, s=65, zorder=4)
        return
    axis.plot(x, y, color=color, linewidth=1.4, alpha=.85)
    for source, face in (('original', color), ('extension', 'white')):
        selected = [(a,b) for a,b,group in zip(x,y,row['sources']) if group == source]
        axis.scatter([point[0] for point in selected], [point[1] for point in selected],
                     facecolor=face, edgecolor=color, linewidth=1.5, s=35, zorder=3)


def decorate(axis, title, bounds):
    axis.axhline(0, color='#555555', linewidth=.7)
    axis.axhline(5, color='#a32626', linewidth=.8, linestyle='--')
    axis.axhline(-5, color='#287440', linewidth=.8, linestyle='--')
    axis.set_title(title, fontsize=11)
    axis.set_xlim(.6,10.4)
    axis.set_ylim(*bounds)
    axis.set_xticks(range(1,11))
    axis.grid(axis='y', alpha=.15)
    axis.spines[['top','right']].set_visible(False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('analysis', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    rows = json.loads(args.analysis.read_text())['groups']
    figure, axes = plt.subplots(2,3,figsize=(12,7))
    for line, metric in enumerate(('frame_p99','processing_cpu_mean')):
        for column, clip in enumerate(CLIPS):
            axis = axes[line,column]
            for row in [item for item in rows if item['clip'] == clip]:
                draw_group(axis,row,metric)
            decorate(axis,clip,limits(rows,metric))
            axis.set_xlabel('Matched repetition')
        axes[line,0].set_ylabel(('Processing p99 change (%)','Process CPU change (%)')[line])
    handles = [Line2D([0],[0],color=COLORS[name],marker='o',label=label)
               for name,label in (('local','B: local USM'),('latency','D: adaptive experiment'))]
    handles += [Line2D([0],[0],color='#555555',linestyle='none',marker='x',label='Duplicate control'),
                Line2D([0],[0],color='#555555',linestyle='none',marker='o',markerfacecolor='white',
                       label='After scope correction')]
    figure.legend(handles=handles,loc='lower center',ncol=4,frameon=False,bbox_to_anchor=(.5,.005))
    figure.suptitle('PERF-15: ten paired trials per option and clip',fontsize=15)
    figure.text(.5,.93,'Lower is better; dashed lines mark the -5% gain and +5% regression thresholds.',
                ha='center',fontsize=10)
    figure.tight_layout(rect=(0,.06,1,.91))
    for suffix in ('.svg','.png'):
        figure.savefig(args.output.with_suffix(suffix),dpi=180,facecolor='white')
    plt.close(figure)


if __name__ == '__main__':
    main()
