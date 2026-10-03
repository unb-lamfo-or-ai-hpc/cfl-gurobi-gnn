# Recorded Zotero developer script

This is the JavaScript executed in Zotero Desktop under **Tools > Developer >
Run JavaScript**, with asynchronous execution enabled, for the previously
authorized six-item membership update. It is not Java and is not part of the
HPC pipeline. The collection and item keys refer to the owner's local library;
they are not portable identifiers or authentication credentials.

```javascript
var collection = Zotero.Collections.getByLibraryAndKey(
  Zotero.Libraries.userLibraryID, 'NNPXWSYK'
);
if (!collection ||
    collection.name !== 'CFL-GNN - Manuscript - Cited References') {
  throw new Error('Collection mismatch');
}
var keys = [
  'JDRQIY4P', 'BUGJ8ZVY', 'FZ979RLZ',
  'CE68X9VZ', 'CP86X653', '7R3T72H3'
];
var items = keys.map(key =>
  Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, key)
);
if (items.some(item => !item || item.deleted || !item.isRegularItem())) {
  throw new Error('Item mismatch');
}
for (var item of items) {
  item.addToCollection(collection.id);
  await item.saveTx();
}
return JSON.stringify({
  collection: collection.key,
  linked: items.map(item => ({
    key: item.key,
    title: item.getField('title')
  }))
});
```

The script links six existing records while preserving their other collection
memberships and bibliographic fields. It does not import papers, generate
BibTeX, or modify Zotero's database directly. Gasse and Cappart were imported
separately through the connector after duplicate and destination checks.
The seven subsequent additions were made by the owner and only read during
the L2O revision. This historical script was not rerun for that revision.
