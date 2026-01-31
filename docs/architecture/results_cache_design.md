# Result Cache Design

## Overview

CausalIQ Workflow Result Caches provide a mechanism for workflow to store
results in a compact and fast results database. It is built on a common
caching infrastructre `TokenClass` which is also used to cache LLM queries and
responses. The common caching infrastructure currently resides in the 
causaliq-knowledge package where the `LLMCacheEntry` specialisation resides,
but the common caching elements will be moved into the causaliq-core package.

## Result Cache Requirements

This section documents the requirements for the Result Cache feature, some
of which differ from the `LLMCache':

### Functional Requirements

- the cache persists between workflows
- each cache entry consists one or more result objects and metadata associated with those objects
- cache entries can be added, updated or deleted
- presence of a cache entry indicates that particular experiment has already been run - 
this is the basis of the CausalIQ Workflow *conservative execution*
- result entries for structure learning will consist of:
  - an encoded graph object representing the learned graph
  - metadata which captures details of the data, algorithm and hyperparameters used,
  the learning process sucha s elapsed time, and of the learned graph such as its
  score
  - optionally, a tabular trace of the learning process, iteration by iteration
- result entries for LLM graph generation will consist of
  - an encoded graph object representing the proposed graph
  - metadata which captures the LLM requests and responses, and about the
  proposed graph asuh as edge confidences
- result caches will typically have up to 10,000 entries, though often 1,000 or less

### Architectural Requirements

- the results cache will be implemented as a sql-lite `.db` database
- the metadata is token-encoded JSON, making use of the `TokenCache` and 
`JSONEncoder` core caching components (currently in causaliq-knowledge)
- concrete implementations of 
