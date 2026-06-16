import subprocess, json, sys

tool = sys.argv[1]   # e.g. open_tab
args_file = sys.argv[2]  # file containing JSON args

with open(args_file) as f:
    args = json.load(f)

args_str = json.dumps(args)
result = subprocess.run(
    ['mavis', 'browser', 'tool', tool, args_str],
    capture_output=True, text=True
)
print(result.stdout)
if result.stderr:
    print('STDERR:', result.stderr, file=sys.stderr)