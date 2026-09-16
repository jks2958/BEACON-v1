# Phase 6 Memory feature contract

The exact ordered contract below is copied from `feature_cols` in the committed Memory preprocessing artifact. The artifact proves model input name and order; it does **not** prove how raw Volatility rows were aggregated into these values.

- Required fields: **94**
- Numeric compatibility: required for every field
- Empirical Volatility reproduction: **unproven**
- Production structured-Volatility inference: **disabled**

Plugin-family entries below are name-prefix observations only, not proven provenance. Metric semantics and original derivations remain unresolved unless an original extractor or paired source is recovered.

| Position | Feature | Prefix observation | Semantics | Reproduction |
|---:|---|---|---|---|
| 0 | `info.Is64` | `info` (inferred) | unknown | unverified |
| 1 | `info.npro` | `info` (inferred) | unknown | unverified |
| 2 | `info.IsPAE` | `info` (inferred) | unknown | unverified |
| 3 | `pslist.nproc` | `pslist` (inferred) | unknown | unverified |
| 4 | `pslist.nppid` | `pslist` (inferred) | unknown | unverified |
| 5 | `pslist.avg_threads` | `pslist` (inferred) | unknown | unverified |
| 6 | `pslist.nprocs64bit` | `pslist` (inferred) | unknown | unverified |
| 7 | `pslist.outfile` | `pslist` (inferred) | unknown | unverified |
| 8 | `dlllist.ndlls` | `dlllist` (inferred) | unknown | unverified |
| 9 | `dlllist.nproc_dll` | `dlllist` (inferred) | unknown | unverified |
| 10 | `dlllist.avg_dllPerProc` | `dlllist` (inferred) | unknown | unverified |
| 11 | `dlllist.avgSize` | `dlllist` (inferred) | unknown | unverified |
| 12 | `dlllist.outfile` | `dlllist` (inferred) | unknown | unverified |
| 13 | `handles.nHandles` | `handles` (inferred) | unknown | unverified |
| 14 | `handles.distinctHandles` | `handles` (inferred) | unknown | unverified |
| 15 | `handles.nproc` | `handles` (inferred) | unknown | unverified |
| 16 | `handles.nAccess` | `handles` (inferred) | unknown | unverified |
| 17 | `handles.avgHandles_per_proc` | `handles` (inferred) | unknown | unverified |
| 18 | `handles.nTypeUnknown` | `handles` (inferred) | unknown | unverified |
| 19 | `handles.nTypePort` | `handles` (inferred) | unknown | unverified |
| 20 | `handles.nTypeProcess` | `handles` (inferred) | unknown | unverified |
| 21 | `handles.nTypeThread` | `handles` (inferred) | unknown | unverified |
| 22 | `handles.nTypeKey` | `handles` (inferred) | unknown | unverified |
| 23 | `handles.nTypeEvent` | `handles` (inferred) | unknown | unverified |
| 24 | `handles.nTypeFile` | `handles` (inferred) | unknown | unverified |
| 25 | `handles.nTypeDirectory` | `handles` (inferred) | unknown | unverified |
| 26 | `handles.nTypeSection` | `handles` (inferred) | unknown | unverified |
| 27 | `handles.nTypeDesktop` | `handles` (inferred) | unknown | unverified |
| 28 | `handles.nTypeToken` | `handles` (inferred) | unknown | unverified |
| 29 | `handles.nTypeMutant` | `handles` (inferred) | unknown | unverified |
| 30 | `handles.nTypeKeyedEvent` | `handles` (inferred) | unknown | unverified |
| 31 | `handles.nTypeSymbolicLink` | `handles` (inferred) | unknown | unverified |
| 32 | `handles.nTypeSemaphore` | `handles` (inferred) | unknown | unverified |
| 33 | `handles.nTypeWindowStation` | `handles` (inferred) | unknown | unverified |
| 34 | `handles.nTypeTimer` | `handles` (inferred) | unknown | unverified |
| 35 | `handles.nTypeIoCompletion` | `handles` (inferred) | unknown | unverified |
| 36 | `handles.nTypeWmiGuid` | `handles` (inferred) | unknown | unverified |
| 37 | `handles.nTypeWaitablePort` | `handles` (inferred) | unknown | unverified |
| 38 | `handles.nTypeJob` | `handles` (inferred) | unknown | unverified |
| 39 | `ldrmodules.total` | `ldrmodules` (inferred) | unknown | unverified |
| 40 | `ldrmodules.not_in_load` | `ldrmodules` (inferred) | unknown | unverified |
| 41 | `ldrmodules.not_in_init` | `ldrmodules` (inferred) | unknown | unverified |
| 42 | `ldrmodules.not_in_mem` | `ldrmodules` (inferred) | unknown | unverified |
| 43 | `ldrmodules.nporc` | `ldrmodules` (inferred) | unknown | unverified |
| 44 | `ldrmodules.not_in_load_avg` | `ldrmodules` (inferred) | unknown | unverified |
| 45 | `ldrmodules.not_in_init_avg` | `ldrmodules` (inferred) | unknown | unverified |
| 46 | `ldrmodules.not_in_mem_avg` | `ldrmodules` (inferred) | unknown | unverified |
| 47 | `malfind.ninjections` | `malfind` (inferred) | unknown | unverified |
| 48 | `malfind.commitCharge` | `malfind` (inferred) | unknown | unverified |
| 49 | `malfind.protection` | `malfind` (inferred) | unknown | unverified |
| 50 | `malfind.uniqueInjections` | `malfind` (inferred) | unknown | unverified |
| 51 | `malfind.avgInjec_per_proc` | `malfind` (inferred) | unknown | unverified |
| 52 | `malfind.tagsVad` | `malfind` (inferred) | unknown | unverified |
| 53 | `malfind.tagsVads` | `malfind` (inferred) | unknown | unverified |
| 54 | `malfind.aveVPN_diff` | `malfind` (inferred) | unknown | unverified |
| 55 | `modules.nmodules` | `modules` (inferred) | unknown | unverified |
| 56 | `modules.avgSize` | `modules` (inferred) | unknown | unverified |
| 57 | `modules.FO_enabled` | `modules` (inferred) | unknown | unverified |
| 58 | `callbacks.ncallbacks` | `callbacks` (inferred) | unknown | unverified |
| 59 | `callbacks.nNoDetail` | `callbacks` (inferred) | unknown | unverified |
| 60 | `callbacks.nBugCheck` | `callbacks` (inferred) | unknown | unverified |
| 61 | `callbacks.nBugCheckReason` | `callbacks` (inferred) | unknown | unverified |
| 62 | `callbacks.nCreateProc` | `callbacks` (inferred) | unknown | unverified |
| 63 | `callbacks.nCreateThread` | `callbacks` (inferred) | unknown | unverified |
| 64 | `callbacks.nLoadImg` | `callbacks` (inferred) | unknown | unverified |
| 65 | `callbacks.nRegisterCB` | `callbacks` (inferred) | unknown | unverified |
| 66 | `callback.nUnknownType` | `callback` (inferred) | unknown | unverified |
| 67 | `modscan.nMod` | `modscan` (inferred) | unknown | unverified |
| 68 | `modscan.nUniqueExt` | `modscan` (inferred) | unknown | unverified |
| 69 | `modscan.nDLL` | `modscan` (inferred) | unknown | unverified |
| 70 | `modscan.nSYS` | `modscan` (inferred) | unknown | unverified |
| 71 | `modscan.nEXE` | `modscan` (inferred) | unknown | unverified |
| 72 | `modscan.nOthers` | `modscan` (inferred) | unknown | unverified |
| 73 | `modscan.AvgSize` | `modscan` (inferred) | unknown | unverified |
| 74 | `modscan.MeanChildExist` | `modscan` (inferred) | unknown | unverified |
| 75 | `modscan.FO_Enabled` | `modscan` (inferred) | unknown | unverified |
| 76 | `mutantscan.nMutantObjects` | `mutantscan` (inferred) | unknown | unverified |
| 77 | `mutantscan.nNamedMutant` | `mutantscan` (inferred) | unknown | unverified |
| 78 | `netscan.nConn` | `netscan` (inferred) | unknown | unverified |
| 79 | `netscan.nDistinctForeignAdd` | `netscan` (inferred) | unknown | unverified |
| 80 | `netscan.nDistinctForeignPort` | `netscan` (inferred) | unknown | unverified |
| 81 | `netscan.nDistinctLocalAddr` | `netscan` (inferred) | unknown | unverified |
| 82 | `netscan.nDistinctLocalPort` | `netscan` (inferred) | unknown | unverified |
| 83 | `netscan.nOwners` | `netscan` (inferred) | unknown | unverified |
| 84 | `netscan.nDistinctProc` | `netscan` (inferred) | unknown | unverified |
| 85 | `netscan.nListening` | `netscan` (inferred) | unknown | unverified |
| 86 | `netscan.Proto_TCPv4` | `netscan` (inferred) | unknown | unverified |
| 87 | `netscan.Proto_TCPv6` | `netscan` (inferred) | unknown | unverified |
| 88 | `netscan.Proto_UDPv4` | `netscan` (inferred) | unknown | unverified |
| 89 | `netscan.Proto_UDPv6` | `netscan` (inferred) | unknown | unverified |
| 90 | `symlinkscan.nLinks` | `symlinkscan` (inferred) | unknown | unverified |
| 91 | `symlinkscan.nFrom` | `symlinkscan` (inferred) | unknown | unverified |
| 92 | `symlinkscan.nTo` | `symlinkscan` (inferred) | unknown | unverified |
| 93 | `symlinkscan.Avg_Children` | `symlinkscan` (inferred) | unknown | unverified |
