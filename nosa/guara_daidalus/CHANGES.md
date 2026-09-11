# DAIDALUS source changes (NOSA 1.3 clause 3.C)

This package does not modify DAIDALUS sources. CMake compiles the pinned tree
`third_party/daidalus` at commit `0647596edb218f8e8c7731ff800396297bbace99`
(tag `DAIDALUSv2.0.3a`) without patches.

Guará wrapper files under this directory are new Apache-2.0 code that call the
unmodified C++ API (`setOwnshipState`, `addTrafficState`, `timeToCorrectiveVolume`,
`set_DO_365B`). Including DAIDALUS in this Larger Work is not a Modification
(NOSA clause 1.F).
