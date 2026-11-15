# Helping with training

[Back to the front page](../README.md#readme)

Some of this project's builds use small neural networks that are trained here, run after run. Invited helpers can lend
a graphics card to that training. A small program on your PC, the **runner**, fetches a training job, trains,
and sends the results back. Every result is then checked on the project's own machine; nothing from your PC is published.

This page explains how to set it up, as simply as possible. It takes about half an hour, plus a large download.

> **For invited helpers.** The runner connects to a private network that helpers are invited to; it does not work
> without that invitation.

## What you need

| | |
|---|---|
| Graphics card | **12 GB of memory or more**, and either an NVIDIA GeForce RTX 30 series or newer, or an AMD Radeon RX 7000 or RX 9000 series card |
| System memory | 32 GB or more (64 GB is better) |
| Free disk space | about 150 GB on an SSD |
| System | Windows 10 (22H2) or Windows 11, or Linux |
| Time | each run keeps the graphics card at full load for about 1.5 to 2 hours |

Training uses the card fully, so it draws as much power and makes as much heat as a demanding game. You decide when
the runner runs.

## Setting up on Windows

> **Radeon cards on Windows:** AMD supports this through WSL for Radeon RX 7000 series cards and some newer ones (see
> [AMD's WSL support list](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/compatibility/compatibilityrad/wsl/wsl_compatibility.html)).
> Radeon RX 6000 cards are not on that list; on those, use Linux instead.

The runner works inside **WSL**, the Linux system built into Windows. Everything it does stays inside it, and it can be
removed completely with one command (see [Removing it](#removing-it)). The same setup works later on a Linux PC.

1. **Update the graphics driver.** NVIDIA: install the newest Game Ready or Studio driver; that is all WSL needs, so do
   not install a driver inside Linux. Radeon: install the newest Adrenalin driver, then, after step 2, AMD's ROCm for
   WSL by following [AMD's WSL guide](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/index.html).
2. **Install Ubuntu in WSL.** Open **Terminal** or **PowerShell** as administrator and run:
   ```
   wsl --install -d Ubuntu-24.04
   ```
   Restart when asked. Ubuntu then opens and asks for a user name and a password for Linux (they do not need to match
   your Windows account).
3. **Check the graphics card.** In the Ubuntu window, run `nvidia-smi` (NVIDIA) or `rocminfo` (Radeon, after AMD's
   ROCm for WSL is installed). It should list your card. If it does not, update the driver (step 1) and restart.
4. **Keep the runner away from Windows (recommended).** In Ubuntu, run:
   ```
   printf '[boot]\nsystemd = true\n[automount]\nenabled = false\n[interop]\nenabled = false\nappendWindowsPath = false\n' | sudo tee /etc/wsl.conf
   ```
   then, in a Windows terminal, `wsl --shutdown`, and open Ubuntu again. Linux then no longer sees your Windows drives
   and cannot start Windows programs.
5. **Join the private network.** In Ubuntu, install Tailscale (a private network between invited PCs; nothing opens
   on your router) and sign in with the invitation you received:
   ```
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up
   ```
   Open the link it prints and sign in. Installing it inside Ubuntu keeps the setup the same when you move to Linux.
6. **Run the setup script.** *(Coming soon: this step is added here once the runner is ready.)* One command builds the
   Python environment for your card (NVIDIA or Radeon), downloads the training code and data (about 100 GB) and shows a key to send to the project. The
   key lets the runner reach one folder on the project's machine, nothing else.

## Setting up on Linux

NVIDIA: install the driver from your distribution and check the card with `nvidia-smi`. Radeon: install ROCm following
[AMD's Linux guide](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/index.html) and check with `rocminfo`. Then follow
steps 5 and 6 above. Radeon RX 6000 cards work only on Linux and have not been tested with this project's training yet.

## Running it

- **Start:** in Ubuntu, `./runner.sh` *(added with step 6)*. It takes the next job, trains, sends the results back and
  waits for the next one.
- **Stop:** press Ctrl+C. A run that is stopped part-way is simply picked up again later or elsewhere.
- **Pause without closing it:** create a file named `pause` in the runner's folder; delete it to continue.
- **Games first:** if the graphics card is busy when a job would start, the runner waits.

## What the runner does and does not do

- It **only connects out** to the project's machine over the private network. Nothing connects into your PC.
- It downloads the training code and data, trains, and sends back the trained results and their logs.
- **Trained results do not stay on your PC:** the runner deletes its local copies after each run.
- It runs the project's training code inside Ubuntu. With step 4 done, that code cannot see your Windows files or start
  Windows programs.
- It collects nothing about you or your PC. Tailscale shows your device name to the network's owner, as any Tailscale
  network does.

## Removing it

In a Windows terminal:
```
wsl --unregister Ubuntu-24.04
```
This deletes the Ubuntu system with the runner, its data and its settings. Uninstall Tailscale from Windows' app list if
you installed it there as well.
