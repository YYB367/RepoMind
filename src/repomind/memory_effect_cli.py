"""Only freezing, offline execution and read-only report viewing are exposed."""
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
    view=actions.add_parser('view',help='Read reports without acquiring the task-service lease')
    view.add_argument('--runs',type=Path,required=True)
    view.add_argument('--port',type=int,default=8772)


def run(args):
    if args.effect_action=='freeze': return freeze_case(args.root,args.db,args.output,args.image)
    if args.effect_action=='offline': return run_offline(args.suite,args.run_dir,args.config_dir)
    from repomind.web.server import WorkbenchServer
    with WorkbenchServer(args.db,args.port,comparison_dir=args.runs) as server:
        server.comparison_only=True
        print('RepoMind 记忆对照：'+server.origin+'/comparisons',flush=True)
        try:server.serve_forever(poll_interval=.25)
        except KeyboardInterrupt:pass
    return {'stopped':True,'new_model_requests':0}
