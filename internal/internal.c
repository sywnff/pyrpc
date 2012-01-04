// Copyright 2011 Netease Inc. All Rights Reserved.
// Author: gzsyw@corp.netease.com (Shi Yanwei)

/*
 *  internal module for py-rpc
 */

#include <Python.h>
#include <inttypes.h>
#include <string.h>
#include <sys/types.h>

typedef u_int8_t uint8;
typedef u_int64_t uint64;

extern uint64 hash3(const uint8*, uint64, uint64);  

static u_int64_t hash_string(const char *data, size_t size) {
  return hash3((unsigned char*)data, size, 0xbeef);
}

static PyObject* Py_hash_string(PyObject *self, PyObject *args) {
  char *from_python = NULL;
  if (!PyArg_Parse(args, "(s)", &from_python))
    return NULL;

  u_int64_t hash = hash_string(from_python, strlen(from_python));
  char buf[32] = {0};
  sprintf(buf, "%llu", (unsigned long long)hash);
  return Py_BuildValue("s", buf);
}


#define MODULE_NAME_MAX_LEN     11
static char _moduleName[MODULE_NAME_MAX_LEN+1] = "_internal";

static struct PyMethodDef pyrpc_internal_methods[] = {
  {"hash_string", Py_hash_string, 1, "create 64 bits hash of string"},
  {0, 0, 0, 0}
};

void init_internal(void) {
  Py_InitModule(_moduleName, pyrpc_internal_methods);
}

