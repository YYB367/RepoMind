"""Explicit offline and approved live pairs; viewing never initiates requests."""
from pathlib import Path
from repomind.memory_effect import freeze_case, run_offline


def add_parser(commands):
    parser=commands.add_parser('memory-compare',help='V4.4 paired memory-effect design and offline workflow')
    actions=parser.add_subparsers(dest='effect_action',required=True)
    freeze=actions.add_parser('freeze',help='Freeze the first pagination case from reviewed pilot memory')
    freeze.add_argument('--root',type=Path,default=Path('.'))
    freeze.add_argument('--output',type=Path,required=True)
    freeze.add_argument('--image',required=True)
    offline=actions.add_parser('offline',help='Run identical scripted actions; no model calls')
    offline.add_argument('--suite',type=Path,default=Path('data/v4.4'))
    offline.add_argument('--run-dir',type=Path,required=True)
    offline.add_argument('--config-dir',type=Path,default=Path('work/docker-v44'))
    live_freeze=actions.add_parser('freeze-live',help='Version the unchanged V4.4 case for the tested live runner; no calls')
    live_freeze.add_argument('--parent',type=Path,default=Path('data/v4.4'))
    live_freeze.add_argument('--output',type=Path,required=True)
    live=actions.add_parser('live',help='One explicitly approved real pair; no retries or overwrite')
    live.add_argument('--suite',type=Path,default=Path('data/v4.4.1'))
    live.add_argument('--run-dir',type=Path,required=True)
    live.add_argument('--config-dir',type=Path,default=Path('work/docker-v44'))
    live.add_argument('--approve-review-sha256',required=True,help='Explicit acknowledgment of the exact reviewed outbound file')
    diagnostic=actions.add_parser('validate-live',help='Supervised simulated responses with real Docker; no model calls')
    diagnostic.add_argument('--suite',type=Path,default=Path('data/v4.4.1'))
    diagnostic.add_argument('--run-dir',type=Path,required=True)
    diagnostic.add_argument('--config-dir',type=Path,default=Path('work/docker-v44'))
    recovery=actions.add_parser('recover',help='Finalize interrupted local evidence without making requests')
    recovery.add_argument('--run-dir',type=Path,required=True)
    recovery.add_argument('--config-dir',type=Path,default=Path('work/docker-v44'))
    recovery.add_argument('--worker-stopped',action='store_true',help='Acknowledge the recorded worker was checked and stopped before recovery')
    view=actions.add_parser('view',help='Read reports without acquiring the task-service lease')
    view.add_argument('--runs',type=Path,required=True)
    view.add_argument('--port',type=int,default=8772)


def run(args):
    if args.effect_action=='freeze': return freeze_case(args.root,args.db,args.output,args.image)
    if args.effect_action=='offline': return run_offline(args.suite,args.run_dir,args.config_dir)
    if args.effect_action in {'freeze-live','live','recover','validate-live'}:
        from repomind.memory_effect_live import freeze_live,run_live,recover
        if args.effect_action=='freeze-live': return freeze_live(args.parent,args.output)
        if args.effect_action=='recover': return recover(args.run_dir,args.config_dir,worker_stopped=args.worker_stopped)
        if args.effect_action=='validate-live':
            from repomind.agent.workspace import digest
            return run_live(args.suite,args.run_dir,args.config_dir,digest(args.suite/'outbound-review.json'),simulation=True)
        return run_live(args.suite,args.run_dir,args.config_dir,args.approve_review_sha256)
    from repomind.web.server import WorkbenchServer
    with WorkbenchServer(args.db,args.port,comparison_dir=args.runs) as server:
        server.comparison_only=True
        print('RepoMind 记忆对照：'+server.origin+'/comparisons',flush=True)
        try:server.serve_forever(poll_interval=.25)
        except KeyboardInterrupt:pass
    return {'stopped':True,'new_model_requests':0}
