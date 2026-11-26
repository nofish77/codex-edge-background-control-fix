"""Extract a known installed CDP implementation for offline mocked tests only."""
import argparse
from pathlib import Path

from repair import ROOT, RepairError, inspect, read_manifest, sha256, transform

SUPPORT = '''
import {EventEmitter as tp} from 'node:events';
const aG=1000, Axe=10000, Pxe=32, rp=Symbol('tab attachment setup');
const LTe=60000;
function K(value){return Number(value);}
const aM=new Set();
function Jt(t){return t.sessionId!=null||t.targetId!=null;}
function an(){return undefined;}
function li(e){return /timed out/i.test(String(e))?'cdp_timeout':'unknown';}
function Dxe(){return {};}
function ze(){}
function us(e){return e.source.sessionId==null;}
function tv(e){return us(e)&&e.source.targetId==null;}
function Fxe(t){return ['alert','confirm','prompt','beforeunload'].includes(t);}
function Uxe(a,b){return a.sessionId!=null?a.sessionId===b.sessionId:a.tabId===b.tabId&&b.sessionId==null;}
function Lxe(p){return Object.fromEntries(Object.entries(p));}
function qxe(e){return {method:e.method,params:e.params,sequence:e.sequence,source:e.source};}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True, type=Path)
    parser.add_argument('--variant', choices=['original', 'patched'], default='patched')
    args = parser.parse_args()
    manifest = read_manifest()
    _, data, state = inspect(args.target, manifest)
    if state == 'unknown':
        raise RepairError('Unrecognized component version; no extraction attempted.')
    if state != args.variant:
        data = transform(data, manifest, reverse=args.variant == 'original')
    text = data.decode('utf-8')
    start = text.index('var ev=class extends tp')
    end = text.index('function Bxe(', start)
    dialog_start = text.index('async function O9(')
    dialog_end = text.index('d();async function up(', dialog_start)
    fixture = SUPPORT + '\n' + text[start:end] + '\n' + text[dialog_start:dialog_end]
    fixture += '\nexport {ev as InstalledCdp,O9 as handleInstalledDialog};\n'
    output = ROOT / '.local' / 'cdp-fixture.mjs'
    output.parent.mkdir(exist_ok=True)
    output.write_text(fixture, encoding='utf-8', newline='')
    (output.parent / 'fixture.sha256').write_text(sha256(data)+'\n', encoding='ascii')
    print(f'Prepared {args.variant} fixture at .local/cdp-fixture.mjs; installed component unchanged. No browser connection was created.')


if __name__ == '__main__':
    main()
