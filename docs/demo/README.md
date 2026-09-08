# Recording the three minute demonstration

The organisers ask for an uncut screen capture of the prototype running one
realistic scenario end to end, with a voice over naming each guardrail as
it fires, under three minutes, and clear about what is synthetic.

1. Start the terminal in the demonstration profile (twelve short scenarios,
   the heavy audits skipped and declared in the ledger, a run of about
   twenty seconds):

       HSL_ASSURANCE=demo HSL_REGISTER=sample_data/register.csv HSL_DEV_MODE=on HSL_TICK_PACE=0 \
       HSL_PORT=8060 python dash_app.py

   With dev mode on, `Developer1` (preparer, function `Developer1`) and
   `Developer2` (approver, function `Developer2`) run a scenario without a
   register entry; the gates record dev mode.

2. Record. Either capture the screen yourself and follow `hsl_demo_script.md`
   (the storyboard with timestamps: the question, the input accepted and a
   file refused by the quarantine, Plan, Gate 1 refused for an unregistered
   approver then approved by a registered SMF, the tape and network live,
   the critic verdict, the ledger, the security posture, the decision gap,
   Gate 2, the briefing, ASK), or let the driver do it:

       pip install playwright && playwright install chromium
       python docs/demo/record_frames.py /tmp/demo_frames
       python docs/demo/assemble_demo.py /tmp/demo_frames /tmp/demo_out

   The driver drives the real terminal and captures four frames a second
   with the time of every cue. The assembler renders the animated intro
   card (`make_intro.py`, in the terminal's own faces), synthesises the
   narration with piper (`pip install piper-tts`; put `en-us-libritts-high.onnx`
   and its `.json` from the piper v0.0.2 release at `~/piper-voices/` or point
   `HSL_DEMO_VOICE` at it; `HSL_DEMO_SPEAKER` picks the voice, `HSL_DEMO_LENGTH`
   the pace), stretches each
   segment so the narration fits, burns the captions, normalises loudness
   and writes `hsl_demo_narrated.mp4`, `hsl_demo_captions.mp4` (no audio,
   for your own voice over), `hsl_demo.srt` and `hsl_demo_script.md`.

3. Before uploading: no confidential or personal data appears (the refused
   file is a two line synthetic example), the length is under 3:00, the
   link works without a login and can be downloaded, and it stays live until
   at least 18 September.

The assembler also lays a synthesised ambient bed under the whole video (`make_ambient.py`, procedural, royalty free by construction) and can splice in a condensed screen recording of your own after the title card: extract its frames, keep motion at double speed and stillness at twenty times, and point `HSL_DEMO_CLIP_KEEP` at the kept frame list.
