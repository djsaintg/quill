"""The look of Quill's main window (colours come from the theme, see themes.py)."""

CSS = """
    Screen { background: $q-bg; color: $q-ink; }
    #title { height: 1; background: $q-panel; color: $q-title; padding: 0 1; text-style: bold; }
    #stage { height: 1fr; padding: 1 1 0 1; }
    #stage.small { padding: 0 1; }
    #quill { width: 34; height: auto; }
    #stage.small #quill { width: 17; height: auto; }
    #stage.small #tail { margin-top: 1; }
    #tail { width: 1; margin-top: 3; color: $q-accent; }
    #bubble { border: round $q-accent; background: $q-bg; padding: 0;
              height: auto; max-height: 100%; scrollbar-size-vertical: 1; }
    #bubble Markdown { background: $q-panel; margin: 0; padding: 0 1; height: auto; }
    #turn { height: auto; display: none; }
    .step { background: $q-panel; color: $q-muted; padding: 0 1; height: 1;
             text-wrap: nowrap; text-overflow: ellipsis; }
    #turn Markdown.after { padding: 1 1 0 1; }
    .step.run { color: $q-accent; }
    .step.err { color: $error; }
    #status { height: 1; color: $q-muted; padding: 0 2; }
    #choices { height: auto; padding: 0 2; display: none; }
    #choices.show { display: block; }
    #choices Button { margin: 0 1 0 0; min-width: 8; }
    #choices Button.picked { background: $q-picked; }
    .sudo-pw { width: 32; border: round $error; background: $q-bg; background-tint: 0%; margin: 0 1 0 0; }
    #title.sudo { background: $q-sudo; }
    #you { height: auto; max-height: 3; color: $q-muted; padding: 0 2; }
    #input { border: round $q-input; background: $q-bg; margin: 0 1; padding: 0 1;
             height: auto; max-height: 10; background-tint: 0%; }
    #input:focus { border: round $q-input; background-tint: 0%; }
    #input .text-area--cursor-line { background: $q-bg; }
    #hints { height: 1; color: $q-hint; padding: 0 2; }
    History { align: center middle; background: $q-bg 80%; }
    #hist { width: 90%; height: 90%; border: round $q-accent; background: $q-bg; padding: 0 1; }
    #hist-title { color: $q-title; text-style: bold; margin-bottom: 1; }
    .who { text-style: bold; margin-top: 1; }
    .who.you { color: $q-title; }
    .who.quill { color: $q-accent; }
    .msg { background: $q-panel; padding: 0 1; margin: 0; }
    Chooser { background: $q-bg; }
    #ch-title { width: 100%; content-align: center middle; height: 3; color: $q-title; text-style: bold; }
    #ch-halves { height: 1fr; }
    .half { width: 1fr; height: 100%; align: center middle; margin: 0 1; }
    .half Static.ch-sprite { width: auto; height: auto; }
    .half Button { width: 20; margin-top: 1; text-style: bold; }
    .half Button:focus { text-style: bold reverse; }
    #ch-foot { width: 100%; content-align: center middle; height: 2; color: $q-hint; }
"""
