# mocap-gait-lab

Headless Unity lab for checking humanoid motion clips (walk, run, idle, actions) before they are used elsewhere.

Unity runs in GitHub Actions (GameCI), plays the clips on a simple capsule-figure rig and renders frames from
several cameras. The frames are uploaded as a workflow artifact so the motion can be reviewed without opening Unity.

## Contents
- `Assets/Editor/MotionLab.cs` - editor script that builds the scene and renders frames.
- `.github/workflows/render.yml` - CI job (Unity under xvfb).

## Data
- Motion capture: CMU Graphics Lab Motion Capture Database (free for any use).
- Figure: capsules placed on the bones of a generic humanoid skeleton.

## Secrets (Settings -> Secrets and variables -> Actions)
- `UNITY_EMAIL`, `UNITY_PASSWORD` - Unity account.
- `UNITY_LICENSE` - contents of the `Unity_lic.ulf` file (Unity Personal).
- `UNITY_SERIAL` - only for Plus/Pro licenses.
