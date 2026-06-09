#!/usr/bin/env python3
"""Patch the sci serve gallery bundle with 3 frontend improvements.

Usage:
    python scripts/patch-gallery-bundle.py          # apply patches
    python scripts/patch-gallery-bundle.py --dry-run # preview only
    python scripts/patch-gallery-bundle.py --check   # verify balance only

Patches:
  1. Auto-fit: image max-h → viewport-relative sizing (calc(100vh-200px))
  2. Auto-fit sidebar: file list → viewport-relative (calc(100vh-120px))
  3. Copy filename state: adds [Dt,ut]=useState for clipboard toggle
  4. Prev/Next + Copy Name buttons: injected after Download button in toolbar

This script is for re-applying when the bundle is regenerated.
"""

import sys
import os

BUNDLE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "src", "science_cli", "serve", "frontend", "assets", "index-B7LEr9BI.js",
)


def is_balanced(s):
    opens = s.count("(") + s.count("[") + s.count("{")
    closes = s.count(")") + s.count("]") + s.count("}")
    return opens == closes, opens - closes


def check_file(path):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        c = f.read()
    bal, diff = is_balanced(c)
    return bal, len(c), diff


def build_patches():
    prev_next_div = (
        'c.jsxs("div",{className:"flex items-center gap-1 border-r border-slate-700/30 pr-2 mr-1",children:['
        + 'c.jsx("button",{onClick:()=>{var $q=(ql||"").toLowerCase(),$fl=ql?B.files.filter(function(f){return f.name.toLowerCase().includes($q)}):B.files,$fi=$fl.findIndex(function(f){return f.path===(X||{}).path});$fi>0&&Tl($fl[$fi-1])},'
        + 'className:"p-1 rounded-md transition-colors "+(function(){var $q=(ql||"").toLowerCase(),$fl=ql?B.files.filter(function(f){return f.name.toLowerCase().includes($q)}):B.files,$fi=$fl.findIndex(function(f){return f.path===(X||{}).path});return $fi<=0?"text-slate-600 cursor-not-allowed":"text-slate-300 hover:bg-slate-700/40"}()),'
        + 'title:"Previous figure",'
        + 'children:[c.jsx("svg",{width:14,height:14,viewBox:"0 0 24 24",fill:"none",stroke:"currentColor",strokeWidth:2,strokeLinecap:"round",strokeLinejoin:"round",children:[c.jsx("path",{d:"m15 18-6-6 6-6"})]})]'
        + '}),'
        + 'c.jsx("button",{onClick:()=>{var $q=(ql||"").toLowerCase(),$fl=ql?B.files.filter(function(f){return f.name.toLowerCase().includes($q)}):B.files,$fi=$fl.findIndex(function(f){return f.path===(X||{}).path});$fi<$fl.length-1&&Tl($fl[$fi+1])},'
        + 'className:"p-1 rounded-md transition-colors "+(function(){var $q=(ql||"").toLowerCase(),$fl=ql?B.files.filter(function(f){return f.name.toLowerCase().includes($q)}):B.files,$fi=$fl.findIndex(function(f){return f.path===(X||{}).path});return $fi>=$fl.length-1?"text-slate-600 cursor-not-allowed":"text-slate-300 hover:bg-slate-700/40"}()),'
        + 'title:"Next figure",'
        + 'children:[c.jsx("svg",{width:14,height:14,viewBox:"0 0 24 24",fill:"none",stroke:"currentColor",strokeWidth:2,strokeLinecap:"round",strokeLinejoin:"round",children:[c.jsx("path",{d:"m9 18 6-6-6-6"})]})]'
        + '})'
        + ']})'
    )
    copy_btn = (
        'c.jsxs("button",{'
        + 'onClick:()=>{navigator.clipboard.writeText(X.name),ut(!0),setTimeout(()=>ut(!1),2e3)},'
        + 'className:"flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-semibold border transition-all bg-slate-800/50 border-slate-700/50 text-slate-300 hover:bg-slate-700/50 hover:border-slate-600",'
        + 'title:"Copy filename to clipboard",'
        + 'children:[c.jsx(Nh,{className:"w-3 h-3"}),c.jsx("span",{children:Dt?"Copied!":"Copy Name"})]'
        + '})'
    )

    edit4_old = '"Download"})]})]})]})'
    edit4_new = '"Download"})]})' + "," + prev_next_div + "," + copy_btn + ']})]})'

    assert is_balanced(prev_next_div)[0], "prev_next_div not balanced"
    assert is_balanced(copy_btn)[0], "copy_btn not balanced"
    assert is_balanced(edit4_old)[1] == is_balanced(edit4_new)[1], "edit4 bracket diff mismatch"

    return [
        ("Auto-fit image", "max-h-[540px] xl:max-h-[600px] object-contain",
         "max-h-[calc(100vh-200px)] object-contain"),
        ("Auto-fit sidebar", "max-h-[640px] xl:max-h-[740px]",
         "max-h-[calc(100vh-120px)]"),
        ("Copy filename state", "[bt,lt]=al.useState(!1)",
         "[bt,lt]=al.useState(!1),[Dt,ut]=al.useState(!1)"),
        ("Prev/Next + Copy Name buttons", edit4_old, edit4_new),
    ]


def main():
    dry_run = "--dry-run" in sys.argv
    check_only = "--check" in sys.argv

    if not os.path.exists(BUNDLE):
        print(f"Error: Bundle not found at {BUNDLE}")
        sys.exit(1)

    with open(BUNDLE) as f:
        content = f.read()

    bal, diff = is_balanced(content)
    if not bal:
        print(f"Warning: Current bundle is unbalanced (diff={diff})")

    if check_only:
        print(f"Bundle: {BUNDLE}")
        print(f"Size: {len(content)} chars")
        print(f"Balance: {'OK' if bal else f'UNBALANCED (diff={diff})'}")
        return

    patches = build_patches()
    print(f"Bundle: {BUNDLE} ({len(content)} chars)")

    # Pre-check: all anchors must exist exactly once (prevents double-patching)
    all_ok = True
    for name, old, _ in patches:
        count = content.count(old)
        if count != 1:
            print(f"  {'✓' if dry_run else '✗'} {name}: anchor {'not found' if count == 0 else f'found {count}x'}")
            if not dry_run:
                all_ok = False

    if not all_ok:
        if dry_run:
            print("\nDRY RUN — not all anchors available (file may already be patched)")
        else:
            print("\nError: Bundle appears already patched or anchors missing — aborting")
            sys.exit(1)
        return

    if dry_run:
        print("\nDRY RUN — all anchors found, no changes written")
        return

    for name, old, new in patches:
        old_diff = is_balanced(old)[1]
        new_diff = is_balanced(new)[1]
        if old_diff != new_diff:
            print(f"  ✗ {name}: bracket diff mismatch (old={old_diff}, new={new_diff})")
            continue
        content = content.replace(old, new, 1)
        print(f"  ✓ {name}")

    bal, diff = is_balanced(content)

    if dry_run:
        print(f"\nAfter patch balance: {'OK' if bal else f'UNBALANCED (diff={diff})'}")
        return

    if not bal:
        print(f"\nError: Resulting bundle is UNBALANCED (diff={diff}) — not saving")
        sys.exit(1)

    with open(BUNDLE, "w") as f:
        f.write(content)

    print(f"\n✓ Patched. {len(content)} chars. Balance: OK")


if __name__ == "__main__":
    main()
