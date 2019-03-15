"""
Code formating, using third party tools.

Superseeds "yapf" feature that was only using one tool for one language.

.. code-block:: shell-session

    $ make format

"""
import functools
import os

from medikit import settings
from medikit.events import subscribe
from medikit.feature import ABSOLUTE_PRIORITY, SUPPORT_PRIORITY, Feature
from medikit.feature.make import which
from medikit.structs import Script


class FormatConfig(Feature.Config):
    python_tools = {"yapf", "black", "isort"}
    javascript_tools = {"prettier"}
    all_tools = functools.reduce(set.union, [javascript_tools, python_tools], set())
    active_tools = set()

    def using(self, *tools):
        for tool in tools:
            if not tool in self.all_tools:
                raise ValueError('Unknown formating tool "{}".'.format(tool))
            self.active_tools.add(tool)


class FormatFeature(Feature):
    Config = FormatConfig

    conflicts = {"yapf"}

    @subscribe("medikit.feature.python.on_generate")
    def on_python_generate(self, event):
        config = self.get_config(event)  # type: FormatConfig
        python = self.get_config(event, "python")
        for tool in FormatConfig.python_tools:
            if tool == "black":
                # Black is only available starting with python 3.6, it will be up to the user to install it.
                continue
            if tool in config.active_tools:
                python.add_requirements(dev=[tool])

    @subscribe("medikit.feature.make.on_generate", priority=SUPPORT_PRIORITY)
    def on_make_generate(self, event):
        config = self.get_config(event)  # type: FormatConfig
        makefile = event.makefile

        if "yapf" in config.active_tools and "black" in config.active_tools:
            raise RuntimeError('Using both "black" and "yapf" does not make sense, choose one.')

        format_script = []

        if "black" in config.active_tools:
            makefile["BLACK"] = which("black")
            makefile["BLACK_OPTIONS"] = "--line-length 120"  # TODO line length global option
            format_script += ["$(BLACK) $(BLACK_OPTIONS) . Projectfile"]

        if "yapf" in config.active_tools:
            makefile["YAPF"] = "$(PYTHON) -m yapf"
            makefile["YAPF_OPTIONS"] = "-rip"
            format_script += ["$(YAPF) $(YAPF_OPTIONS) . Projectfile"]

        if "isort" in config.active_tools:
            makefile["ISORT"] = "$(PYTHON) -m isort"
            makefile["ISORT_OPTIONS"] = "--recursive --apply"
            format_script += ["$(ISORT) $(ISORT_OPTIONS) . Projectfile"]

        if "prettier" in config.active_tools:
            makefile["PRETTIER"] = which("prettier")
            makefile["PRETTIER_OPTIONS"] = "--write"
            makefile["PRETTIER_PATTERNS"] = "**/*.\{j,t\}s **/*.\{j,t\}sx \!docs/**"
            format_script += ["$(PRETTIER) $(PRETTIER_OPTIONS) $(PRETTIER_PATTERNS)"]

        makefile.add_target(
            "format",
            Script("\n".join(format_script)),
            deps=("install-dev",),
            phony=True,
            doc="Reformats the codebase (with " + ", ".join(sorted(config.active_tools)) + ").",
        )

    @subscribe("medikit.on_start", priority=SUPPORT_PRIORITY)
    def on_start(self, event):
        self.render_file(".style.yapf", "yapf/style.yapf.j2")

    @subscribe("medikit.on_start", priority=ABSOLUTE_PRIORITY - 1)
    def on_before_start(self, event):
        style_config = os.path.join(os.getcwd(), ".style.yapf")
        if os.path.exists(style_config):
            self.dispatcher.info("YAPF_STYLE_CONFIG = " + style_config)
            settings.YAPF_STYLE_CONFIG = style_config