# Removing `art::Ptr` from LArSoft modules

Appendix A of *Migrating to Phlex* (phlex-examples `migration/doc/art_ptr_removal.rst`,
commit 5df307b). The Phlex team wrote it as an AI memory file, so it is reproduced nearly
verbatim. Apply the rules mechanically, but still review every case that touches written
associations, `.key()` chaining, or pointers stored beyond the event.

## Goal

Identify `*_module.cc` files that use `art::Ptr`/`fill_ptr_vector` but do not need to, that
is, they never place an `art::Ptr`-based product into the event.

A module needs `art::Ptr` if it puts into the event:

- `art::Assns`
- `art::PtrVector`
- `art::PtrMaker`-produced pointers
- `std::vector<art::Ptr<T>>`

## Finding candidates

`art_inventory.py report` shows `art::Ptr`, `fill_ptr_vector`, `FindManyP` and `produces`
lines per file. The guide's own tree-walking script:

```python
import os, re
srcs = '/path/to/srcs'
no_ptr_output = []
for root, dirs, files in os.walk(srcs, followlinks=True):  # followlinks needed for symlinked repos
    for fname in files:
        if not fname.endswith('_module.cc'): continue
        fpath = os.path.join(root, fname)
        with open(fpath) as fh: content = fh.read()
        if 'art::Ptr<' not in content and 'fill_ptr_vector' not in content: continue
        has_output = (re.search(r'\bart::Assns\b', content) or
                      re.search(r'\bart::PtrVector\b', content) or
                      re.search(r'\bart::PtrMaker\b', content) or
                      (re.search(r'vector\s*<\s*art::Ptr\s*<', content) and re.search(r'\.\s*put\s*\(', content)))
        if not has_output:
            no_ptr_output.append(fpath[len(srcs)+1:])
```

## Replacement patterns

### Single-element access from a handle

```cpp
// Before
art::Handle<std::vector<T>> h; evt.getByLabel(label, h);
art::Ptr<T> p(h, 0);
p->method();

// After
T const& p = evt.getProduct<std::vector<T>>(label).at(0);
p.method();
```

### Loop-local pointer construction

When `art::Ptr` is used only within a loop body and not stored or returned:

```cpp
// Before
for (size_t i = 0; i < h->size(); ++i) {
    art::Ptr<T> p(h, i);
    p->method();
}

// After
for (size_t i = 0; i < h->size(); ++i) {
    T const& p = h->at(i);
    p.method();
}
// Or use range-based for with getProduct:
for (T const& p : evt.getProduct<std::vector<T>>(label)) { p.method(); }
```

### `fill_ptr_vector` and `FindManyP` to `getHandle` and `FindMany`

When `fill_ptr_vector` feeds `FindManyP` and only object access is needed:

```cpp
// Before
art::Handle<std::vector<T>> h;
std::vector<art::Ptr<T>> v;
if (evt.getByLabel(label, h)) art::fill_ptr_vector(v, h);
art::FindManyP<U> fm(v, evt, label2);
std::vector<art::Ptr<U>> items = fm.at(i);
items[j]->method();

// After
auto const h = evt.getHandle<std::vector<T>>(label);
if (!h) return;
art::FindMany<U> fm(h, evt, label2);
std::vector<U const*> const& items = fm.at(i);
items[j]->method();  // syntax unchanged
```

Check the "Before" control flow before copying the `if (!h) return;`: if the original went
on to do other work when the product was missing, an early return changes behaviour.

### `fill_ptr_vector` for passing hits to `BackTrackerService`

```cpp
// Before
std::vector<art::Ptr<recob::Hit>> allhits;
art::fill_ptr_vector(allhits, hithdl);

// After: build pointer vector directly; avoids art::Ptr overhead
auto const hithdl = e.getValidHandle<std::vector<recob::Hit>>(label);
std::vector<recob::Hit const*> allhits;
allhits.reserve(hithdl->size());
for (auto const& hit : *hithdl) allhits.push_back(&hit);
```

`BackTrackerService` has `std::vector<recob::Hit const*>` overloads for `GetSetOfTrackIds`,
`HitCollectionPurity`, and `HitCollectionEfficiency`. (Kit note: confirm the overloads exist
in the LArSoft version the target repository builds against.)

### `FindOneP` to `FindOne`

- `FindOneP<T>::at(i)` returns `art::Ptr<T>` (use `->`)
- `FindOne<T>::at(i)` returns `cet::maybe_ref<T const>` (use `.ref().`)
- Header: `canvas/Persistency/Common/FindOne.h`

### Method signatures taking `art::Ptr` by const reference

```cpp
// Before
void f(art::Ptr<T> const& p) { p->method(); }

// After
void f(T const& p)            { p.method();  }
```

### Collection parameter preference order

1. `std::vector<T> const&`: pass the product vector directly (e.g. `*handle`); cleanest.
2. `std::vector<T const*> const&`: raw pointer vector, when a direct reference is not
   feasible (e.g. a filtered subset).
3. `std::vector<art::Ptr<T>>`: avoid; only justified when `.key()` is needed for
   association chaining inside the helper.

### Handle acquisition preference order

1. `evt.getProduct<C>(tag)`: first choice whenever the handle is not needed downstream;
   returns `C const&`; throws `art::Exception` automatically if missing; also remove
   `#include "art/Framework/Principal/Handle.h"` if no `art::Handle` type remains.
2. `evt.getValidHandle<C>(tag)`: when a handle object is required (e.g. to construct
   `FindMany`/`FindManyP`); product must always be present; no explicit validity check.
3. `evt.getHandle<C>(tag)`: only when the product may legitimately be absent; test with
   `if (!h)`, never `.isValid()`.
4. `evt.getByLabel(tag, h)`: obsolete two-argument form; always replace.

Additional rules:

- `art::Handle` objects must never be data members of a module class.
- Data products (pointers, references, IDs) must never be cached as class data members across
  events; obtain them locally in `analyze()`/`produce()`/etc.
- If existing code throws when a handle is invalid, replace with `getProduct` (no handle
  needed) or `getValidHandle` (handle needed) and remove the manual check.
- When a cached data-product pointer or reference is removed from a class, update helper
  method signatures to accept the collection by `const&` and pass it at every call site.

## `FindMany` versus `FindManyP`

- `FindMany<T>` when only the pointed-to objects are needed (no chaining); returns `T const*`.
- `FindManyP<T>` when association chaining is required; `art::Ptr<T>::key()` is the correct,
  safe way to index into the next association query.
- Never use pointer arithmetic (`ptr - handle->data()`) as a substitute for `.key()`.
- A module may legitimately include `FindManyP.h` alongside `FindMany.h` when it chains
  associations, even if it outputs no `art::Ptr`-based products.
- Kit note: the switch also changes the failure mode. When an association points into a
  product that is not available, `FindMany` gives a null pointer, and `art::Ptr::get()` can
  return null where `*p` or `p->` would throw an art exception. If the original relied on that
  exception, keep the dereference where the original made it, or check for null at that point
  and throw. Resolving every pointer up front (for example converting a whole `FindManyP`
  result to raw pointers before the loop) changes when, and whether, the exception fires.
  Confirm the behaviour in the canvas version the repository builds against.
- Kit note, accepted pattern: extracted code cannot hold an `art::Ptr`, so keeping a lazy
  dereference is usually impossible. Resolve eagerly at the boundary with
  `T const* raw = ptr.operator->();`, which is the same code path as the original `ptr->x`,
  so null and unavailable pointers fail the same way the original did, only earlier. Do not
  use `&*ptr` or `ptr.get()`: in canvas 3.17 `operator*` is `*get()` and `get()` returns
  `nullptr` for a null `Ptr`, so `&*ptr` dereferences a null pointer where `ptr->` went to
  `parentProduct_()` (checked in `canvas/Persistency/Common/Ptr.h`, canvas 3.17.0). Record
  the earlier failure point in the notes as an error-path deviation. This is acceptable when
  every pointer points into a product the module already fetched with `getValidHandle`, so
  the failure cannot happen on ordinary input. Otherwise ask the human.

## Includes to remove

When no `art::Ptr` remains:

- `canvas/Persistency/Common/Ptr.h`
- `canvas/Persistency/Common/FindManyP.h`: replace with `FindMany.h` only when there is no
  association chaining
- `lardata/Utilities/AssociationUtil.h` (if only used for `fill_ptr_vector`)

When no `art::Handle` remains:

- `art/Framework/Principal/Handle.h`

## Completed example: `RecoCheckAna_module.cc`

`larsim/larsim/MCCheater/RecoCheckAna_module.cc` in LArSoft:

- removed `FindManyP.h` and `Ptr.h`; replaced with `FindMany.h`,
- all `std::vector<art::Ptr<recob::Hit>>` replaced with `std::vector<recob::Hit const*>`,
- `fill_ptr_vector` replaced by direct pointer construction from `getValidHandle`,
- all `FindManyP` replaced with `FindMany` throughout helper methods,
- `BackTrackerService` calls updated to non-Ptr overloads,
- modern C++ throughout: structured bindings, range-for, if-with-initializer.
