"""Build derived duration-enabled voices once; never patch a voice per request."""
import hashlib
import json
from pathlib import Path
import sys

def prepare(folder):
    import onnx
    from piper.patch_voice_with_alignment import add_alignment_output
    for name in ('es_ES-sharvard-medium.onnx','en_GB-cori-medium.onnx'):
        source=folder/name;target=folder/(name+'.aligned.onnx');marker=target.with_suffix('.sha256')
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        if target.is_file() and marker.is_file() and marker.read_text()==digest:
            continue
        graph=onnx.load(source);add_alignment_output(graph)
        temporary=target.with_suffix('.partial');onnx.save(graph,temporary);temporary.replace(target)
        marker.write_text(digest)
        del graph
    print(json.dumps({'alignment_voices':'ready'}))

if __name__=='__main__':prepare(Path(sys.argv[1]))
