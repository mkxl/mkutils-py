import dataclasses
import inspect
from typing import Any, ClassVar, Optional, Self

from typer import Typer

from mkutils.typing import Function, SyncFunction
from mkutils.utils import Utils


@dataclasses.dataclass(kw_only=True)
class Cli:
    DEFAULT_ADD_DEFAULT_CALLBACK: ClassVar[bool] = True
    DEFAULT_PRETTY_EXCEPTIONS_ENABLE: ClassVar[bool] = False

    typer: Typer

    @classmethod
    def new(
        cls,
        *,
        add_default_callback: bool = DEFAULT_ADD_DEFAULT_CALLBACK,
        pretty_exceptions_enable: bool = DEFAULT_PRETTY_EXCEPTIONS_ENABLE,
    ) -> Self:
        typer = cls._typer(pretty_exceptions_enable=pretty_exceptions_enable)
        cli = cls(typer=typer)

        cli._init(add_default_callback=add_default_callback)

        return cli

    @classmethod
    def _typer(cls, *, pretty_exceptions_enable: bool) -> Typer:
        return Typer(pretty_exceptions_enable=pretty_exceptions_enable)

    @staticmethod
    def _default_callback() -> None:
        pass

    def add_callback(self, *, fn: SyncFunction[Any, Any]) -> Self:
        self.typer.callback()(fn)

        return self

    def _init(self, *, add_default_callback: bool) -> None:
        if add_default_callback:
            self.add_callback(fn=self._default_callback)

    def add_command(self, *, name: Optional[str] = None, fn: Function[Any, Any]) -> Self:
        if inspect.iscoroutinefunction(fn):
            fn = Utils.to_sync_fn(fn)

        self.typer.command(name=name)(fn)

        return self

    def run(self) -> None:
        self.typer()
