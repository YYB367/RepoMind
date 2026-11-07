"""Export existing V4.2 receipts and raw trials without rerunning a model."""
import argparse
import json
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',type=Path,required=True)
    parser.add_argument('--prefix',required=True)
    parser.add_argument('--phase',choices=('dev','holdout'),required=True)
    parser.add_argument('--output-dir',type=Path,default=Path('reports/v4.2'))
    args=parser.parse_args()
    targets=[(args.run_dir/(args.phase+'.json'),args.output_dir/(args.prefix+'-'+args.phase+'.json'))]
    if args.phase=='dev': targets.append((args.run_dir/'selection-lock.json',args.output_dir/(args.prefix+'-selection-lock.json')))
    raw_target=args.output_dir/(args.prefix+'-'+args.phase+'-trials.jsonl')
    if raw_target.exists() or any(target.exists() for _,target in targets):
        raise ValueError('preserve existing exports; choose a new prefix')
    for source,_ in targets:
        if not source.is_file(): raise ValueError('phase has no complete report; retain partial runtime evidence')
    args.output_dir.mkdir(parents=True,exist_ok=True)
    for source,target in targets:
        with target.open('xb') as stream: stream.write(source.read_bytes())
    trials=[]
    for path in sorted((args.run_dir/args.phase).glob('repeat-*/*/*/result.json')):
        trials.append({'split':args.phase,'trial':json.loads(path.read_text(encoding='utf-8'))})
    if len(trials)!=sum(row['tasks'] for row in json.loads(targets[0][0].read_text())['metrics'].values()):
        raise ValueError('trial count differs from phase summary')
    with raw_target.open('x',encoding='utf-8',newline='\n') as stream:
        for row in trials: stream.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
    print(f'Exported {len(trials)} existing {args.phase} trials; no model requests issued.')


if __name__=='__main__': main()
