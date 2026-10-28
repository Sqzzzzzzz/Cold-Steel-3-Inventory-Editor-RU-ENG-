"""Read-only quantity changes relative to the opened file; no file IO."""
from dataclasses import dataclass
from cs3_save import CS3Save


@dataclass(frozen=True)
class ItemChange:
    item_id: int
    before: int
    after: int

    @property
    def kind(self):
        return 'added' if self.before==0 else 'removed' if self.after==0 else 'modified'


class EditChanges:
    def __init__(self):
        self._original=None
        self.before={}
        self.current={}
        self.changes={}
        self.reordered=False

    def refresh(self,save):
        if save is None:
            self._original=None;self.before={};self.current={};self.changes={};self.reordered=False
            return
        # The engine retains immutable original bytes across undo/reset. Read
        # them once per baseline; never change the engine's saved snapshots.
        if self._original is not save._original:
            self._original=save._original
            self.before={item.item_id:item.quantity for item in CS3Save(self._original).items()}
        self.current={item.item_id:item.quantity for item in save.items()}
        self.changes={i:ItemChange(i,self.before.get(i,0),self.current.get(i,0))
                      for i in sorted(self.before.keys()|self.current.keys())
                      if self.before.get(i,0)!=self.current.get(i,0)}
        self.reordered=([i for i in self.before if i in self.current]
                        !=[i for i in self.current if i in self.before])

    def counts(self):
        return {kind:sum(change.kind==kind for change in self.changes.values())
                for kind in ('added','removed','modified')}
