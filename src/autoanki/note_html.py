basic_before = """<!doctype html>
<html class="mac chrome" dir="ltr" data-bs-theme="light">
<head>
    <title>previewer</title>
<link rel="stylesheet" type="text/css" href="http://127.0.0.1:55593/_anki/css/webview.css"><style>
body { zoom: 1; background-color: var(--canvas); }
html { font-family:"Helvetica"; }
:root.system-font-size, :root.night-mode.system-font-size { font-size: 13.0px; --bs-body-font-size: 13.0px; --font-size: 13.0px; }

button {
    --canvas: #fff;
    -webkit-appearance: none;
    background: var(--canvas);
    border-radius: var(--border-radius);
    padding: 3px 12px;
    border: 1px solid var(--border);
    box-shadow: 0px 1px 3px var(--border-subtle);
    font-family: Helvetica
}
.night-mode button { --canvas: #606060; --fg: #eee; }

:root { --canvas: #f5f5f5 }
:root[class*=night-mode] { --canvas: #2c2c2c }
.card {
    font-family: arial;
    font-size: 20px;
    text-align: center;
    color: black;
}
</style>
<link rel="stylesheet" type="text/css" href="http://127.0.0.1:55593/_anki/css/reviewer.css">
<script type="text/javascript" src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.5/MathJax.js?config=TeX-AMS-MML_HTMLorMML"></script>
</head>

<body class="isMac reduce-motion fancy">
<p class='card'>"""

basic_between = "</p><hr id='answer'><p class='card'>"
basic_after = """</p>
             </body></html>
             """
