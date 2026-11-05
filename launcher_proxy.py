"""Forward launcher calls to their real binary with rice-local configuration."""
import json
import os
import sys

def forwarded_arguments(arguments,defaults):
    result=[];i=0
    groups={'-config':('-config','-theme','-no-config'),'-theme':('-config','-theme','-no-config'),'--conf':('--conf','-c'),'--style':('--style','-s'),'-plugin-path':('-plugin-path',),'--config':('--config',)}
    while i<len(defaults):
        flag=defaults[i];value=defaults[i+1];i+=2
        if not any(arg==candidate or arg.startswith(candidate+'=') for candidate in groups.get(flag,(flag,)) for arg in arguments):result.extend((flag,value))
    return [*result,*arguments]

if __name__=='__main__':
    binding=json.loads(open(os.environ['QQS_LAUNCHER_BINDINGS'],encoding='utf-8').read())[sys.argv[1]]
    os.environ.update(binding.get('environment',{}))
    if binding.get('cwd'):os.chdir(binding['cwd'])
    arguments=forwarded_arguments(sys.argv[2:],binding['arguments']) if binding.get('forward_options',True) else [*binding['arguments'],*sys.argv[2:]]
    os.execv(binding['binary'],[binding['binary'],*arguments])
