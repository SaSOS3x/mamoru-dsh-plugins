#!/usr/bin/env python3
"""Download spark profiles and decode them offline to the JSON of the spark viewer - script of the tps-optimization-neoforge
skill (written in the DeceasedCraft port, 2026-10-08, v26; moved into the skill 2026-10-27).

Why: the spark viewer (https://spark.lucko.me/<id>) decodes the profile in the browser / on its server; a plain fetch of
the page gives the viewer app, not the data. bytebin serves the raw payload: https://spark-usercontent.lucko.me/<id>,
Content-Type application/x-spark-sampler (or -health / -heap) = one protobuf message (SamplerData / HealthData /
HeapData), not gzipped. This script decodes it with a small protobuf wire-format reader (pure Python, no pip installs)
driven by FIELDS below, and writes the same JSON text as the viewer's raw page https://spark.lucko.me/<id>?raw=1&full=true
(verified byte-identical, sha256, on 10 profiles 2026-10-08) - so spark_summary.py reads it unchanged.

Schema: FIELDS is transcribed from the viewer's own proto (github lucko/spark-viewer proto/spark.proto; the proto files are
not shipped with the skill, FIELDS is all the script needs); it names the JSON keys. The plugin's protos (lucko/spark
spark-common/src/main/proto/spark/spark.proto + spark_sampler.proto) have the same field numbers but snake_case names, some renamed
(creator -> user, platform_metadata -> platform, builtin -> builtIn, spark_data_version -> sparkVersion) and one field the
viewer does not know: PlatformMetadata 9 spark_version (string, e.g. "1.10.124") - the viewer drops it, so does the JSON;
the summary below prints it ("spark x.y.z").

Viewer raw JSON shape (what this writes):
  {"type": "sampler", <every field of SamplerData in .proto order>}; every message carries ALL its fields in .proto order:
  absent scalar = default (0 / "" / false), absent message = null, repeated = [], map = {} (JS object key order: integer
  keys ascending first, then insertion order), int64 = number, enum = NUMBER (not the name), double printed like
  JavaScript (4.0 -> 4, 1e-7 -> 1e-7, NaN/Infinity -> null). Thread call trees are the flat full=true format:
  threads[] {name, time:0, children[] = FLAT node list, times[] (one per time window), childrenRefs[] = roots};
  node {time:0, children:[], className, methodName, parentLineNumber, lineNumber, methodDesc, times[], childrenRefs[]}.
  Option --enum-names writes enum NAMES instead of numbers (then the file is no longer byte-identical to the viewer's).
  bytes fields (channelInfo.publicKey, only in live viewer sessions) are written as base64 strings - not verified.

  python spark_fetch.py <id|url|file.bin> [...] [--out spark_profiles] [--enum-names] [--check] [--quiet]
    keeps <out>/<id>.bin (raw download, reused when present unless --refetch) and writes <out>/<id>.json,
    prints a summary (threads / nodes, sampler mode, interval, start, duration, time windows) and with --check
    internal consistency checks (times length == time windows, childrenRefs in range, one parent per node, thread time
    == sum of the roots per window, sampled time <= window duration).
"""
import argparse, base64, datetime, gzip, hashlib, json, math, os, re, struct, sys, urllib.request

BYTEBIN = 'https://spark-usercontent.lucko.me/'
DEFAULT_OUT = 'spark_profiles'  # relative to the current folder: never inside the skill (a skill install folder)
CONTENT_TYPES = {'application/x-spark-sampler': 'sampler', 'application/x-spark-heap': 'heap',
                 'application/x-spark-health': 'health'}
ROOT_MESSAGE = {'sampler': 'SamplerData', 'heap': 'HeapData', 'health': 'HealthData'}

# ------------------------------------------------------------------------------------------------------------------
# Field tables. message -> [(field number, json name, type, label)], in .proto declaration order (= JSON key order).
# type: int32 int64 uint32 double string bool bytes | enum:<Enum> | msg:<Message> | map:<keytype>:<valuetype>
# label: '' single, 'rep' repeated (packed or not), 'map'
# ------------------------------------------------------------------------------------------------------------------
RAV = 'msg:RollingAverageValues'
FIELDS = {
    # spark_sampler
    'SamplerData': [
        (1, 'metadata', 'msg:SamplerMetadata', ''), (2, 'threads', 'msg:ThreadNode', 'rep'),
        (3, 'classSources', 'map:string:string', 'map'), (4, 'methodSources', 'map:string:string', 'map'),
        (5, 'lineSources', 'map:string:string', 'map'), (6, 'timeWindows', 'int32', 'rep'),
        (7, 'timeWindowStatistics', 'map:int32:msg:WindowStatistics', 'map'),
        (8, 'channelInfo', 'msg:SocketChannelInfo', '')],
    'SamplerMetadata': [
        (1, 'user', 'msg:CommandSenderMetadata', ''), (2, 'startTime', 'int64', ''), (3, 'interval', 'int32', ''),
        (4, 'threadDumper', 'msg:SamplerMetadata.ThreadDumper', ''),
        (5, 'dataAggregator', 'msg:SamplerMetadata.DataAggregator', ''), (6, 'comment', 'string', ''),
        (7, 'platform', 'msg:PlatformMetadata', ''), (8, 'platformStatistics', 'msg:PlatformStatistics', ''),
        (9, 'systemStatistics', 'msg:SystemStatistics', ''), (10, 'serverConfigurations', 'map:string:string', 'map'),
        (11, 'endTime', 'int64', ''), (12, 'numberOfTicks', 'int32', ''),
        (13, 'sources', 'map:string:msg:PluginOrModMetadata', 'map'),
        (14, 'extraPlatformMetadata', 'map:string:string', 'map'),
        (15, 'samplerMode', 'enum:SamplerMetadata.SamplerMode', ''),
        (16, 'samplerEngine', 'enum:SamplerMetadata.SamplerEngine', ''),
        (17, 'samplerEngineVersion', 'string', ''), (18, 'metrics', 'msg:Metrics', '')],
    'SamplerMetadata.ThreadDumper': [
        (1, 'type', 'enum:SamplerMetadata.ThreadDumper.Type', ''), (2, 'ids', 'int64', 'rep'),
        (3, 'patterns', 'string', 'rep')],
    'SamplerMetadata.DataAggregator': [
        (1, 'type', 'enum:SamplerMetadata.DataAggregator.Type', ''),
        (2, 'threadGrouper', 'enum:SamplerMetadata.DataAggregator.ThreadGrouper', ''),
        (3, 'tickLengthThreshold', 'int64', ''), (4, 'numberOfIncludedTicks', 'int32', '')],
    'ThreadNode': [
        (1, 'name', 'string', ''), (2, 'time', 'double', ''), (3, 'children', 'msg:StackTraceNode', 'rep'),
        (4, 'times', 'double', 'rep'), (5, 'childrenRefs', 'int32', 'rep')],
    'StackTraceNode': [
        (1, 'time', 'double', ''), (2, 'children', 'msg:StackTraceNode', 'rep'), (3, 'className', 'string', ''),
        (4, 'methodName', 'string', ''), (5, 'parentLineNumber', 'int32', ''), (6, 'lineNumber', 'int32', ''),
        (7, 'methodDesc', 'string', ''), (8, 'times', 'double', 'rep'), (9, 'childrenRefs', 'int32', 'rep')],
    # spark_heap
    'HeapData': [(1, 'metadata', 'msg:HeapMetadata', ''), (2, 'entries', 'msg:HeapEntry', 'rep')],
    'HeapEntry': [(1, 'order', 'int32', ''), (2, 'instances', 'int32', ''), (3, 'size', 'int64', ''),
                  (4, 'type', 'string', '')],
    # spark (common)
    'HealthData': [
        (1, 'metadata', 'msg:HealthMetadata', ''),
        (2, 'timeWindowStatistics', 'map:int32:msg:WindowStatistics', 'map'),
        (3, 'channelInfo', 'msg:SocketChannelInfo', '')],
    'HealthMetadata': [
        (1, 'user', 'msg:CommandSenderMetadata', ''), (2, 'platform', 'msg:PlatformMetadata', ''),
        (3, 'platformStatistics', 'msg:PlatformStatistics', ''), (4, 'systemStatistics', 'msg:SystemStatistics', ''),
        (5, 'generatedTime', 'int64', ''), (6, 'serverConfigurations', 'map:string:string', 'map'),
        (7, 'sources', 'map:string:msg:PluginOrModMetadata', 'map'),
        (8, 'extraPlatformMetadata', 'map:string:string', 'map'), (9, 'metrics', 'msg:Metrics', '')],
    'PlatformMetadata': [
        (1, 'type', 'enum:PlatformMetadata.Type', ''), (2, 'name', 'string', ''), (3, 'version', 'string', ''),
        (4, 'minecraftVersion', 'string', ''), (7, 'sparkVersion', 'int32', ''), (8, 'brand', 'string', '')],
    'SystemStatistics': [
        (1, 'cpu', 'msg:SystemStatistics.Cpu', ''), (2, 'memory', 'msg:SystemStatistics.Memory', ''),
        (3, 'gc', 'map:string:msg:SystemStatistics.Gc', 'map'), (4, 'disk', 'msg:SystemStatistics.Disk', ''),
        (5, 'os', 'msg:SystemStatistics.Os', ''), (6, 'java', 'msg:SystemStatistics.Java', ''),
        (7, 'uptime', 'int64', ''), (8, 'net', 'map:string:msg:SystemStatistics.NetInterface', 'map'),
        (9, 'jvm', 'msg:SystemStatistics.Jvm', '')],
    'SystemStatistics.Cpu': [
        (1, 'threads', 'int32', ''), (2, 'processUsage', 'msg:SystemStatistics.Cpu.Usage', ''),
        (3, 'systemUsage', 'msg:SystemStatistics.Cpu.Usage', ''), (4, 'modelName', 'string', '')],
    'SystemStatistics.Cpu.Usage': [(1, 'last1m', 'double', ''), (2, 'last15m', 'double', '')],
    'SystemStatistics.Memory': [
        (1, 'physical', 'msg:SystemStatistics.Memory.MemoryPool', ''),
        (2, 'swap', 'msg:SystemStatistics.Memory.MemoryPool', '')],
    'SystemStatistics.Memory.MemoryPool': [(1, 'used', 'int64', ''), (2, 'total', 'int64', '')],
    'SystemStatistics.Gc': [(1, 'total', 'int64', ''), (2, 'avgTime', 'double', ''), (3, 'avgFrequency', 'double', '')],
    'SystemStatistics.Disk': [(1, 'used', 'int64', ''), (2, 'total', 'int64', '')],
    'SystemStatistics.Os': [(1, 'arch', 'string', ''), (2, 'name', 'string', ''), (3, 'version', 'string', '')],
    'SystemStatistics.Java': [(1, 'vendor', 'string', ''), (2, 'version', 'string', ''),
                              (3, 'vendorVersion', 'string', ''), (4, 'vmArgs', 'string', '')],
    'SystemStatistics.Jvm': [(1, 'name', 'string', ''), (2, 'vendor', 'string', ''), (3, 'version', 'string', '')],
    'SystemStatistics.NetInterface': [
        (1, 'rxBytesPerSecond', RAV, ''), (2, 'txBytesPerSecond', RAV, ''),
        (3, 'rxPacketsPerSecond', RAV, ''), (4, 'txPacketsPerSecond', RAV, '')],
    'PlatformStatistics': [
        (1, 'memory', 'msg:PlatformStatistics.Memory', ''), (2, 'gc', 'map:string:msg:PlatformStatistics.Gc', 'map'),
        (3, 'uptime', 'int64', ''), (4, 'tps', 'msg:PlatformStatistics.Tps', ''),
        (5, 'mspt', 'msg:PlatformStatistics.Mspt', ''), (6, 'ping', 'msg:PlatformStatistics.Ping', ''),
        (7, 'playerCount', 'int64', ''), (8, 'world', 'msg:WorldStatistics', ''),
        (9, 'onlineMode', 'enum:PlatformStatistics.OnlineMode', '')],
    'PlatformStatistics.Memory': [
        (1, 'heap', 'msg:MemoryUsage', ''), (2, 'nonHeap', 'msg:MemoryUsage', ''),
        (3, 'pools', 'msg:PlatformStatistics.Memory.MemoryPool', 'rep'),
        (4, 'allocBpsLast1m', RAV, ''), (5, 'allocBpsLast5m', RAV, ''), (6, 'allocBpsLast15m', RAV, '')],
    'PlatformStatistics.Memory.MemoryPool': [
        (1, 'name', 'string', ''), (2, 'usage', 'msg:MemoryUsage', ''), (3, 'collectionUsage', 'msg:MemoryUsage', '')],
    'PlatformStatistics.Gc': [(1, 'total', 'int64', ''), (2, 'avgTime', 'double', ''),
                              (3, 'avgFrequency', 'double', '')],
    'PlatformStatistics.Tps': [(1, 'last1m', 'double', ''), (2, 'last5m', 'double', ''), (3, 'last15m', 'double', ''),
                               (4, 'gameTargetTps', 'int32', '')],
    'PlatformStatistics.Mspt': [(1, 'last1m', RAV, ''), (2, 'last5m', RAV, ''), (3, 'gameMaxIdealMspt', 'int32', '')],
    'PlatformStatistics.Ping': [(1, 'last15m', RAV, '')],
    'WorldStatistics': [
        (1, 'totalEntities', 'int32', ''), (2, 'entityCounts', 'map:string:int32', 'map'),
        (3, 'worlds', 'msg:WorldStatistics.World', 'rep'), (4, 'gameRules', 'msg:WorldStatistics.GameRule', 'rep'),
        (5, 'dataPacks', 'msg:WorldStatistics.DataPack', 'rep')],
    'WorldStatistics.World': [(1, 'name', 'string', ''), (2, 'totalEntities', 'int32', ''),
                              (3, 'regions', 'msg:WorldStatistics.Region', 'rep')],
    'WorldStatistics.Region': [(1, 'totalEntities', 'int32', ''), (2, 'chunks', 'msg:WorldStatistics.Chunk', 'rep')],
    'WorldStatistics.Chunk': [(1, 'x', 'int32', ''), (2, 'z', 'int32', ''), (3, 'totalEntities', 'int32', ''),
                              (4, 'entityCounts', 'map:string:int32', 'map')],
    'WorldStatistics.GameRule': [(1, 'name', 'string', ''), (2, 'defaultValue', 'string', ''),
                                 (3, 'worldValues', 'map:string:string', 'map')],
    'WorldStatistics.DataPack': [(1, 'name', 'string', ''), (2, 'description', 'string', ''),
                                 (3, 'source', 'string', ''), (4, 'builtIn', 'bool', '')],
    'WindowStatistics': [
        (1, 'ticks', 'int32', ''), (2, 'cpuProcess', 'double', ''), (3, 'cpuSystem', 'double', ''),
        (4, 'tps', 'double', ''), (5, 'msptMedian', 'double', ''), (6, 'msptMax', 'double', ''),
        (7, 'players', 'int32', ''), (8, 'entities', 'int32', ''), (9, 'tileEntities', 'int32', ''),
        (10, 'chunks', 'int32', ''), (11, 'startTime', 'int64', ''), (12, 'endTime', 'int64', ''),
        (13, 'duration', 'int32', '')],
    'RollingAverageValues': [(1, 'mean', 'double', ''), (2, 'max', 'double', ''), (3, 'min', 'double', ''),
                             (4, 'median', 'double', ''), (5, 'percentile95', 'double', '')],
    'MemoryUsage': [(1, 'used', 'int64', ''), (2, 'committed', 'int64', ''), (3, 'init', 'int64', ''),
                    (4, 'max', 'int64', '')],
    'DoubleMetricSeries': [(1, 'startTimestampMs', 'int64', ''), (2, 'timestampDeltasMs', 'uint32', 'rep'),
                           (3, 'values', 'double', 'rep')],
    'AveragesMetricSeries': [(1, 'startTimestampMs', 'int64', ''), (2, 'timestampDeltasMs', 'uint32', 'rep'),
                             (3, 'values', RAV, 'rep')],
    'MemoryUsageMetricSeries': [(1, 'startTimestampMs', 'int64', ''), (2, 'timestampDeltasMs', 'uint32', 'rep'),
                                (3, 'values', 'msg:MemoryUsage', 'rep')],
    'WorldInfoMetricSeries': [(1, 'startTimestampMs', 'int64', ''), (2, 'timestampDeltasMs', 'uint32', 'rep'),
                              (3, 'values', 'msg:WorldInfoMetricSeries.Values', 'rep')],
    'WorldInfoMetricSeries.Values': [(1, 'players', 'int32', ''), (2, 'entities', 'int32', ''),
                                     (3, 'tileEntities', 'int32', ''), (4, 'chunks', 'int32', '')],
    'Metrics': [
        (1, 'tps', 'msg:DoubleMetricSeries', ''), (2, 'tickDuration', 'msg:AveragesMetricSeries', ''),
        (3, 'cpuUsageProcess', 'msg:DoubleMetricSeries', ''), (4, 'cpuUsageSystem', 'msg:DoubleMetricSeries', ''),
        (5, 'memoryUsageHeap', 'msg:MemoryUsageMetricSeries', ''),
        (6, 'memoryUsageNonHeap', 'msg:MemoryUsageMetricSeries', ''),
        (7, 'memoryAllocation', 'msg:DoubleMetricSeries', ''), (8, 'worldInfo', 'msg:WorldInfoMetricSeries', ''),
        (9, 'playerPing', 'msg:AveragesMetricSeries', '')],
    'CommandSenderMetadata': [(1, 'type', 'enum:CommandSenderMetadata.Type', ''), (2, 'name', 'string', ''),
                              (3, 'uniqueId', 'string', '')],
    'PluginOrModMetadata': [(1, 'name', 'string', ''), (2, 'version', 'string', ''), (3, 'author', 'string', ''),
                            (4, 'description', 'string', ''), (5, 'builtIn', 'bool', '')],
    'SocketChannelInfo': [(1, 'channelId', 'string', ''), (2, 'publicKey', 'bytes', '')],
}
FIELDS['HeapMetadata'] = FIELDS['HealthMetadata']

ENUMS = {
    'PlatformMetadata.Type': ['SERVER', 'CLIENT', 'PROXY', 'APPLICATION'],
    'PlatformStatistics.OnlineMode': ['UNKNOWN', 'OFFLINE', 'ONLINE'],
    'CommandSenderMetadata.Type': ['OTHER', 'PLAYER'],
    'SamplerMetadata.ThreadDumper.Type': ['ALL', 'SPECIFIC', 'REGEX'],
    'SamplerMetadata.DataAggregator.Type': ['SIMPLE', 'TICKED'],
    'SamplerMetadata.DataAggregator.ThreadGrouper': ['BY_NAME', 'BY_POOL', 'AS_ONE'],
    'SamplerMetadata.SamplerMode': ['EXECUTION', 'ALLOCATION', 'LOCK'],
    'SamplerMetadata.SamplerEngine': ['JAVA', 'ASYNC'],
}

# fields of the plugin's proto that the viewer proto lacks (decoded only for the summary, not written to the JSON)
PLUGIN_ONLY = {('PlatformMetadata', 9): ('sparkVersionString', 'string')}

# ------------------------------------------------------------------------------------------------------------------
# wire format
# ------------------------------------------------------------------------------------------------------------------
_D = struct.Struct('<d')
_F = struct.Struct('<f')
M64 = (1 << 64) - 1


class ProtoError(Exception):
    pass


def read_varint(buf, pos):
    result = shift = 0
    while True:
        if pos >= len(buf):
            raise ProtoError('truncated varint')
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if b < 0x80:
            return result, pos
        shift += 7
        if shift > 70:
            raise ProtoError('varint too long')


def conv_varint(v, t):
    if t == 'int32' or t.startswith('enum:'):
        v &= 0xFFFFFFFF
        return v - (1 << 32) if v >= 1 << 31 else v
    if t == 'int64':
        v &= M64
        v = v - (1 << 64) if v >= 1 << 63 else v
        return v if abs(v) <= 1 << 53 else int(float(v))   # JS number (protobuf-ts long_type_number)
    if t == 'uint32':
        return v & 0xFFFFFFFF
    if t == 'bool':
        return v != 0
    raise ProtoError(f'varint for type {t}')


def scalar_default(t):
    if t == 'string':
        return ''
    if t == 'bool':
        return False
    if t == 'bytes':
        return ''
    if t == 'double':
        return 0.0
    return 0


def new_message(name):
    o = {}
    for _, jn, t, label in FIELDS[name]:
        if label == 'rep':
            o[jn] = []
        elif label == 'map':
            o[jn] = {}
        elif t.startswith('msg:'):
            o[jn] = None
        else:
            o[jn] = scalar_default(t)
    return o


_INDEX = {}


def field_index(name):
    idx = _INDEX.get(name)
    if idx is None:
        idx = _INDEX[name] = {f[0]: f for f in FIELDS[name]}
    return idx


class Decoder:
    def __init__(self):
        self.unknown = {}      # (message, field number) -> count
        self.plugin_only = {}  # (message, field number) -> last value

    def skip(self, buf, pos, wt):
        if wt == 0:
            return read_varint(buf, pos)[1]
        if wt == 1:
            return pos + 8
        if wt == 2:
            n, pos = read_varint(buf, pos)
            return pos + n
        if wt == 5:
            return pos + 4
        raise ProtoError(f'unsupported wire type {wt}')

    def read_scalar(self, buf, pos, wt, t):
        """one scalar value at pos (not packed)"""
        if t == 'double':
            if wt != 1:
                raise ProtoError(f'double with wire type {wt}')
            return _D.unpack_from(buf, pos)[0], pos + 8
        if t in ('string', 'bytes'):
            if wt != 2:
                raise ProtoError(f'{t} with wire type {wt}')
            n, pos = read_varint(buf, pos)
            raw = bytes(buf[pos:pos + n])
            val = raw.decode('utf-8', 'replace') if t == 'string' else base64.b64encode(raw).decode('ascii')
            return val, pos + n
        if wt != 0:
            raise ProtoError(f'{t} with wire type {wt}')
        v, pos = read_varint(buf, pos)
        return conv_varint(v, t), pos

    def decode(self, buf, name, start=0, end=None, target=None):
        if end is None:
            end = len(buf)
        o = target if target is not None else new_message(name)
        idx = field_index(name)
        pos = start
        while pos < end:
            tag, pos = read_varint(buf, pos)
            fn, wt = tag >> 3, tag & 7
            f = idx.get(fn)
            if f is None:
                key = (name, fn)
                if key in PLUGIN_ONLY and wt == 2:
                    self.plugin_only[key], pos = self.read_scalar(buf, pos, wt, PLUGIN_ONLY[key][1])
                else:
                    self.unknown[key] = self.unknown.get(key, 0) + 1
                    pos = self.skip(buf, pos, wt)
                continue
            _, jn, t, label = f
            if label == 'map':
                n, pos = read_varint(buf, pos)
                k, v = self.decode_map_entry(buf, pos, pos + n, t)
                o[jn][k] = v
                pos += n
            elif t.startswith('msg:'):
                if wt != 2:
                    raise ProtoError(f'{name}.{jn}: message with wire type {wt}')
                n, pos = read_varint(buf, pos)
                if label == 'rep':
                    o[jn].append(self.decode(buf, t[4:], pos, pos + n))
                else:   # a repeated occurrence of a singular message merges into it
                    o[jn] = self.decode(buf, t[4:], pos, pos + n, o[jn])
                pos += n
            elif label == 'rep':
                if wt == 2 and t not in ('string', 'bytes'):   # packed
                    n, pos = read_varint(buf, pos)
                    stop = pos + n
                    lst = o[jn]
                    if t == 'double':
                        cnt = n // 8
                        lst.extend(struct.unpack_from(f'<{cnt}d', buf, pos))
                        pos = stop
                    else:
                        while pos < stop:
                            v, pos = read_varint(buf, pos)
                            lst.append(conv_varint(v, t))
                    if pos != stop:
                        raise ProtoError(f'{name}.{jn}: packed field overrun')
                else:
                    v, pos = self.read_scalar(buf, pos, wt, t)
                    o[jn].append(v)
            else:
                o[jn], pos = self.read_scalar(buf, pos, wt, t)
        if pos != end:
            raise ProtoError(f'{name}: message overrun ({pos} != {end})')
        return o

    def decode_map_entry(self, buf, pos, end, t):
        _, kt, vt = t.split(':', 2)
        k = scalar_default(kt)
        v = None
        while pos < end:
            tag, pos = read_varint(buf, pos)
            fn, wt = tag >> 3, tag & 7
            if fn == 1:
                k, pos = self.read_scalar(buf, pos, wt, kt)
            elif fn == 2:
                if vt.startswith('msg:'):
                    n, pos = read_varint(buf, pos)
                    v = self.decode(buf, vt[4:], pos, pos + n, v)
                    pos += n
                else:
                    v, pos = self.read_scalar(buf, pos, wt, vt)
            else:
                pos = self.skip(buf, pos, wt)
        if v is None:
            v = new_message(vt[4:]) if vt.startswith('msg:') else scalar_default(vt)
        if kt == 'bool':
            k = 'true' if k else 'false'
        return str(k), v


# ------------------------------------------------------------------------------------------------------------------
# JSON text exactly like JavaScript's JSON.stringify
# ------------------------------------------------------------------------------------------------------------------
def js_number(x):
    if isinstance(x, bool):
        return 'true' if x else 'false'
    if isinstance(x, int):
        return str(x)
    if math.isnan(x) or math.isinf(x):
        return 'null'
    if x == 0:
        return '0'
    r = repr(x)
    sign = ''
    if r[0] == '-':
        sign, r = '-', r[1:]
    mant, _, exp = r.partition('e')
    exp = int(exp) if exp else 0
    ip, _, fp = mant.partition('.')
    digits = (ip + fp).lstrip('0')
    lead = len(ip + fp) - len((ip + fp).lstrip('0'))
    n = len(ip) + exp - lead          # value = 0.digits * 10^n
    digits = digits.rstrip('0') or '0'
    k = len(digits)
    if k <= n <= 21:
        s = digits + '0' * (n - k)
    elif 0 < n <= 21:
        s = digits[:n] + '.' + digits[n:]
    elif -6 < n <= 0:
        s = '0.' + '0' * (-n) + digits
    else:
        e = n - 1
        es = ('+' if e >= 0 else '-') + str(abs(e))
        s = (digits[0] + ('.' + digits[1:] if k > 1 else '')) + 'e' + es
    return sign + s


_ARRAY_INDEX = re.compile(r'^(0|[1-9][0-9]*)$')


def js_key_order(keys):
    """JS objects list integer-like keys (array indexes) first, ascending, then the others in insertion order"""
    idx = [k for k in keys if _ARRAY_INDEX.match(k) and int(k) < 4294967295]
    if not idx:
        return list(keys)
    s = set(idx)
    return sorted(idx, key=int) + [k for k in keys if k not in s]


def js_dumps(v, out):
    if v is None:
        out.append('null')
    elif isinstance(v, str):
        out.append(json.dumps(v, ensure_ascii=False))
    elif isinstance(v, (bool, int, float)):
        out.append(js_number(v))
    elif isinstance(v, list):
        out.append('[')
        first = True
        for x in v:
            if not first:
                out.append(',')
            first = False
            js_dumps(x, out)
        out.append(']')
    elif isinstance(v, dict):
        out.append('{')
        first = True
        for k in js_key_order(v.keys()):
            if not first:
                out.append(',')
            first = False
            out.append(json.dumps(k, ensure_ascii=False))
            out.append(':')
            js_dumps(v[k], out)
        out.append('}')
    else:
        raise TypeError(type(v))


def enum_names(o, name):
    """replace enum numbers by names in place (option --enum-names)"""
    if o is None:
        return
    for _, jn, t, label in FIELDS[name]:
        if t.startswith('enum:'):
            vals = ENUMS[t[5:]]
            conv = (lambda x: vals[x] if 0 <= x < len(vals) else x)
            o[jn] = [conv(x) for x in o[jn]] if label == 'rep' else conv(o[jn])
        elif label == 'map' and ':msg:' in t:
            for x in o[jn].values():
                enum_names(x, t.split(':msg:')[1])
        elif t.startswith('msg:') and t[4:] not in ('StackTraceNode',):
            if label == 'rep':
                for x in o[jn]:
                    enum_names(x, t[4:])
            else:
                enum_names(o[jn], t[4:])


# ------------------------------------------------------------------------------------------------------------------
# fetch / summary / checks
# ------------------------------------------------------------------------------------------------------------------
def fetch(pid):
    req = urllib.request.Request(BYTEBIN + pid, headers={
        'User-Agent': 'spark_fetch.py (tps-optimization-neoforge skill)', 'Accept': ','.join(CONTENT_TYPES)})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
        ctype = (r.headers.get('Content-Type') or '').split(';')[0].strip()
        if (r.headers.get('Content-Encoding') or '').lower() == 'gzip':
            data = gzip.decompress(data)
    return data, ctype


def fmt_ts(ms):
    if not ms:
        return '?'
    t = datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc)
    return t.astimezone().strftime('%Y-%m-%d %H:%M:%S %z') + ' (UTC ' + t.strftime('%H:%M:%S') + ')'


def enum_name(enum, v):
    vals = ENUMS[enum]
    return v if isinstance(v, str) else (vals[v] if 0 <= v < len(vals) else str(v))


def summary(pid, kind, data, dec):
    lines = []
    md = data.get('metadata') or {}
    if kind != 'sampler':
        lines.append(f'{pid}: {kind}')
        return lines
    pl = md.get('platform') or {}
    sv = dec.plugin_only.get(('PlatformMetadata', 9)) or f"data v{pl.get('sparkVersion')}"
    da = md.get('dataAggregator') or {}
    td = md.get('threadDumper') or {}
    st, et = md.get('startTime') or 0, md.get('endTime') or 0
    mode = enum_name('SamplerMetadata.SamplerMode', md.get('samplerMode', 0))
    engine = enum_name('SamplerMetadata.SamplerEngine', md.get('samplerEngine', 0))
    lines.append(f"{pid}: {pl.get('brand')} {pl.get('version')} mc {pl.get('minecraftVersion')} spark {sv}"
                 f"  by {(md.get('user') or {}).get('name')}  comment {md.get('comment')!r}")
    unit = 'bytes' if mode == 'ALLOCATION' else 'ms'
    lines.append(f"  sampler {mode} / {engine} {md.get('samplerEngineVersion') or ''}  interval "
                 f"{md.get('interval', 0) / 1000:g} ms" + (' (alloc: bytes per sample)' if mode == 'ALLOCATION' else '')
                 + f"  aggregator {enum_name('SamplerMetadata.DataAggregator.Type', da.get('type', 0))}"
                 f" grouper {enum_name('SamplerMetadata.DataAggregator.ThreadGrouper', da.get('threadGrouper', 0))}"
                 + (f"  ticks-over {da.get('tickLengthThreshold')} ms ({da.get('numberOfIncludedTicks')} ticks included)"
                    if da.get('tickLengthThreshold') else '')
                 + f"  dumper {enum_name('SamplerMetadata.ThreadDumper.Type', td.get('type', 0))}"
                 f" ids {td.get('ids')} patterns {td.get('patterns')}")
    lines.append(f"  start {fmt_ts(st)}  duration {(et - st) / 1000:.1f} s  ticks {md.get('numberOfTicks')}"
                 f"  time windows {len(data.get('timeWindows') or [])}  classSources {len(data.get('classSources') or {})}"
                 f"  methodSources {len(data.get('methodSources') or {})}  sources {len(md.get('sources') or {})}")
    for t in data.get('threads') or []:
        tot = sum(t.get('times') or [])
        lines.append(f"  thread {t.get('name')!r}: {len(t.get('children') or [])} nodes, {len(t.get('childrenRefs') or [])}"
                     f" roots, sampled {tot / 1000 if unit == 'ms' else tot:.1f} {'s' if unit == 'ms' else 'bytes'}")
    tws = data.get('timeWindowStatistics') or {}
    for w in js_key_order(tws.keys()):
        s = tws[w]
        lines.append(f"  window {w}: {fmt_ts(s.get('startTime')).split(' (')[0][11:19]} +{s.get('duration', 0) / 1000:.1f}s"
                     f"  ticks {s.get('ticks')} tps {s.get('tps', 0):.2f}  mspt median {s.get('msptMedian', 0):.2f}"
                     f" max {s.get('msptMax', 0):.1f}  cpu proc {s.get('cpuProcess', 0) * 100:.0f}% sys"
                     f" {s.get('cpuSystem', 0) * 100:.0f}%  players {s.get('players')} entities {s.get('entities')}"
                     f" tiles {s.get('tileEntities')} chunks {s.get('chunks')}")
    if dec.unknown:
        lines.append(f'  WARNING fields unknown to the schema (skipped): {dec.unknown}')
    return lines


def check(data):
    """internal consistency of a decoded sampler profile; returns a list of problems (empty = OK)"""
    errs = []
    md = data.get('metadata') or {}
    nwin = len(data.get('timeWindows') or [])
    tws = data.get('timeWindowStatistics') or {}
    if sorted(map(str, data.get('timeWindows') or [])) != sorted(tws.keys()):
        errs.append(f'timeWindows {data.get("timeWindows")} != timeWindowStatistics keys {list(tws)}')
    interval_ms = (md.get('interval') or 0) / 1000
    execution = md.get('samplerMode', 0) in (0, 'EXECUTION')
    # spark itself can book one sample of a child into a different window than its parent (seen once in wQ7GKI6j7C:
    # Thread.runWith 56912 ms vs its only child 56916 ms in window 0, same bytes in the viewer) - up to one sample of
    # excess is a note, more is a problem
    notes = []
    for t in data.get('threads') or []:
        nodes = t.get('children') or []
        nm = t.get('name')
        if len(t.get('times') or []) != nwin:
            errs.append(f'{nm}: thread times length {len(t.get("times") or [])} != {nwin} windows')
        parents = [0] * len(nodes)
        badlen = bad = small = 0
        tol = interval_ms if execution else 0
        for i, n in enumerate(nodes):
            if len(n['times']) != nwin:
                badlen += 1
            for c in n['childrenRefs']:
                if not 0 <= c < len(nodes):
                    errs.append(f'{nm}: node {i} childrenRefs {c} out of range')
                else:
                    parents[c] += 1
            # a parent's time per window >= the sum of its children's
            for w in range(min(nwin, len(n['times']))):
                excess = sum(nodes[c]['times'][w] for c in n['childrenRefs'] if 0 <= c < len(nodes)) - n['times'][w]
                if excess > tol + 1e-6:
                    bad += 1
                    break
                if excess > 1e-6:
                    small += 1
                    break
        if badlen:
            errs.append(f'{nm}: {badlen} nodes whose times length != {nwin} windows')
        if bad:
            errs.append(f'{nm}: {bad} nodes whose children have more time than the node (> one sample)')
        if small:
            notes.append(f'note {nm}: {small} nodes whose children have up to one sample more than the node (spark)')
        roots = t.get('childrenRefs') or []
        for r in roots:
            if not 0 <= r < len(nodes):
                errs.append(f'{nm}: root {r} out of range')
            elif parents[r]:
                errs.append(f'{nm}: root {r} also has a parent')
        rset = set(roots)
        orphans = sum(1 for i, p in enumerate(parents) if p == 0 and i not in rset)
        multi = sum(1 for p in parents if p > 1)
        if orphans or multi:
            errs.append(f'{nm}: {orphans} nodes without parent, {multi} with several parents')
        if nodes and roots:
            for w in range(nwin):
                rs = sum(nodes[r]['times'][w] for r in roots if 0 <= r < len(nodes))
                if abs(rs - t['times'][w]) > 1e-6:
                    errs.append(f'{nm}: window {w}: thread time {t["times"][w]} != roots sum {rs}')
                    break
        if execution:
            for w, key in enumerate(js_key_order(tws.keys())):
                dur = tws[key].get('duration') or 0
                if dur and t['times'][w] > dur + 2 * interval_ms + 50:
                    errs.append(f'{nm}: window {key}: sampled {t["times"][w]} ms > window duration {dur} ms')
    return errs, notes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('ids', nargs='+', help='spark ids, https://spark.lucko.me/<id> links or local .bin files')
    ap.add_argument('--out', default=DEFAULT_OUT, help='folder for <id>.bin / <id>.json (default: spark_profiles in the current folder)')
    ap.add_argument('--type', default=None, choices=sorted(ROOT_MESSAGE), help='payload type of a local file')
    ap.add_argument('--enum-names', action='store_true', help='write enum names instead of numbers (not viewer-exact)')
    ap.add_argument('--refetch', action='store_true', help='download again even if <id>.bin exists')
    ap.add_argument('--check', action='store_true', help='internal consistency checks of the call trees')
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rc = 0
    for arg in a.ids:
        kind = a.type
        if os.path.isfile(arg):
            pid = os.path.splitext(os.path.basename(arg))[0]
            with open(arg, 'rb') as f:
                raw = f.read()
            kind = kind or 'sampler'
        else:
            m = re.search(r'([A-Za-z0-9]{6,})/?(?:\?.*)?$', arg.strip())
            if not m:
                print(f'{arg}: not an id / link / file', file=sys.stderr)
                rc = 1
                continue
            pid = m.group(1)
            binp = os.path.join(a.out, pid + '.bin')
            if os.path.isfile(binp) and not a.refetch:
                with open(binp, 'rb') as f:
                    raw = f.read()
                kind = kind or 'sampler'
            else:
                raw, ctype = fetch(pid)
                kind = CONTENT_TYPES.get(ctype)
                if kind is None:
                    print(f'{pid}: unexpected Content-Type {ctype!r} ({len(raw)} bytes) - not saved', file=sys.stderr)
                    rc = 1
                    continue
                with open(binp, 'wb') as f:
                    f.write(raw)
        dec = Decoder()
        try:
            body = dec.decode(memoryview(raw), ROOT_MESSAGE[kind])
        except (ProtoError, struct.error, IndexError) as e:
            print(f'{pid}: decode failed: {e}', file=sys.stderr)
            rc = 1
            continue
        data = {'type': kind}
        data.update(body)
        if a.enum_names:
            enum_names(body, ROOT_MESSAGE[kind])
        out = []
        js_dumps(data, out)
        txt = ''.join(out)
        jp = os.path.join(a.out, pid + '.json')
        with open(jp, 'w', encoding='utf-8', newline='') as f:
            f.write(txt)
        if not a.quiet:
            print('\n'.join(summary(pid, kind, data, dec)))
            print(f'  -> {jp} ({len(txt.encode("utf-8"))} bytes, sha256 {hashlib.sha256(txt.encode("utf-8")).hexdigest()})')
        if a.check and kind == 'sampler':
            errs, notes = check(data)
            print(f'  check: ' + ('OK' if not errs else 'PROBLEMS'))
            for e in errs[:20] + notes:
                print('    ' + e)
            rc = rc or (1 if errs else 0)
    return rc


if __name__ == '__main__':
    sys.exit(main())
