# SSH + password hardening (do this FIRST on any jailbroken device)

Everyone on your Wi-Fi knows `root:alpine` and `mobile:alpine`. Change both now.

## Change the passwords (NewTerm on-device, or SSH)

```bash
su            # password: alpine (becomes root)
passwd        # type NEW root password twice (nothing echoes — normal)
passwd mobile # type NEW mobile password twice
exit
```

Verify: `ssh root@YOUR-IP` should now reject `alpine` and accept the new one.

## Lock down further (optional, recommended)

- Turn off SSH when not using it: Cydia → OpenSSH is always-on by design.
  Install `SSLPatch`-era alternative? Simplest real control: in SBSettings-style
  toggles, or just `launchctl unload /Library/LaunchDaemons/com.openssh.sshd.plist`
  when idle, `load` when needed:
  ```bash
  launchctl unload /Library/LaunchDaemons/com.openssh.sshd.plist  # SSH off
  launchctl load /Library/LaunchDaemons/com.openssh.sshd.plist    # SSH on
  ```
- Change the default `mobile` password too (done above) — App Store/iTunes
  sync processes run as mobile.
- Never expose port 22 to the internet (router port-forward). LAN-only.

## If `alpine` doesn't work (password unknown)

You can't recover it — you replace it. Options in order:
1. `passwd` via any existing root shell (NewTerm already root? just run `passwd`).
2. Volume-Up boot (tweaks off, SSH still runs) → `ssh root@IP` with `alpine` →
   if THAT works, the password was fine and something else blocked you.
3. Filza (runs as root) → edit is awkward; prefer: Filza's built-in terminal?
   Use NewTerm. If no terminal works, the last resort is a restore — talk first.
