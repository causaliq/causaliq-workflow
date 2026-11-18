# Add describe-cache CLI command

Add a new `describe-cache` CLI command which provides some basic
information about the specified cache. This should prove useful especially
when caches are partitioned into different kinds of intermediate results.

The command syntax is:

```bash
cqflow describe-cache -i <cache-path>
```

Initially this writes output to the terminal (although later it might be
useful to draw plots or write to caches as part of a workflow). The output
contains:

- full path name of the file and its size on disk in K/M/GByte
- object type of the cache (PDG, DAG, metrics etc)
- number of entries in cache total possible/total with an entry/total with
  an object
- then, for each variable in the key schema:

  - name and type of the variable
  - list of possible values for the variable, and for each value a count
    of total possible/total with an entry/total with an object

- an example entry, ideally with an object

## Further work which is out of scope for this task

These are deliberately outside this task:

1. __Declared matrix values__

   - Accept a declared matrix so "possible" counts include values that
     were never attempted, not only those observed in the cache.

1. __Object presence without decompression__

   - Add a `WorkflowCache` API that reports which entries hold an object
     without decompressing their payloads, so very large graph caches can
     be described quickly.

1. __Description as a workflow output__

   - Write the description to a cache, or plot it, as part of a workflow.
