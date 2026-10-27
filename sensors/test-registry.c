#define _GNU_SOURCE
/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <unistd.h>
#include "hexagonrpcd/apps_std.c"

int main(void)
{
    char root[]="/tmp/vermeer-registry-test-XXXXXX";
    assert(mkdtemp(root));
    struct hexagonfs_dirent state={.name="/",.ops=&hexagonfs_mapped_rw_ops,.u.phys=root};
    struct apps_std_ctx ctx={0};
    ctx.rootfd=hexagonfs_open_root(ctx.fds,&state);
    ctx.adsp_library_dirfd=ctx.rootfd;
    assert(ctx.rootfd>=0);
    char name[]="/sns_reg_version",mode[]="wb",invalid[]="wtf",contents[]="version=14";
    struct fastrpc_io_buffer in[5]={{0}},out[1]={{0}};
    uint32_t descriptor=0,request[2],written[2];
    in[1]=(struct fastrpc_io_buffer){.p=name,.s=sizeof(name)};
    in[2]=(struct fastrpc_io_buffer){.p=invalid,.s=sizeof(invalid)};
    out[0]=(struct fastrpc_io_buffer){.p=&descriptor,.s=sizeof(descriptor)};
    assert(apps_std_fopen(&ctx,in,out)==AEE_EBADPARM);
    in[2]=(struct fastrpc_io_buffer){.p=mode,.s=sizeof(mode)};
    assert(apps_std_fopen(&ctx,in,out)==0);
    request[0]=descriptor;request[1]=sizeof(contents);
    in[0]=(struct fastrpc_io_buffer){.p=request,.s=sizeof(request)};
    in[1]=(struct fastrpc_io_buffer){.p=contents,.s=sizeof(contents)};
    out[0]=(struct fastrpc_io_buffer){.p=written,.s=sizeof(written)};
    assert(apps_std_fwrite(&ctx,in,out)==0 && written[0]==sizeof(contents) && !written[1]);
    assert(hexagonfs_close(ctx.fds,descriptor)==0);
    assert(hexagonfs_rename(ctx.fds,ctx.rootfd,"/sns_reg_version","/temporary")==0);
    assert(hexagonfs_rename(ctx.fds,ctx.rootfd,"/temporary","/sns_reg_version")==0);
    descriptor=hexagonfs_openat(ctx.fds,ctx.rootfd,ctx.rootfd,"sns_reg_version");
    uint32_t seek[3]={descriptor,(uint32_t)-2,2};
    in[0]=(struct fastrpc_io_buffer){.p=seek,.s=sizeof(seek)};
    assert(apps_std_fseek(&ctx,in,out)==0);
    char tail[2];assert(hexagonfs_read(ctx.fds,descriptor,2,tail)==2 && tail[0]=='4' && !tail[1]);
    seek[2]=3;assert(apps_std_fseek(&ctx,in,out)==AEE_EBADPARM);
    assert(hexagonfs_lseek(ctx.fds,descriptor,0,SEEK_SET)==0);
    char readback[32]={0};
    assert(hexagonfs_read(ctx.fds,descriptor,sizeof(readback),readback)==sizeof(contents));
    assert(!strcmp(readback,contents));
    assert(hexagonfs_close(ctx.fds,descriptor)==0);
    assert(hexagonfs_openat_mode(ctx.fds,ctx.rootfd,ctx.rootfd,"new",O_WRONLY|O_CREAT)>=0);
    char path[512];snprintf(path,sizeof(path),"%s/link",root);
    assert(symlink("/tmp/escape",path)==0);
    assert(hexagonfs_openat_mode(ctx.fds,ctx.rootfd,ctx.rootfd,"link",O_WRONLY|O_CREAT)<0);
    for(int i=0;i<HEXAGONFS_MAX_FD;i++)if(ctx.fds[i])hexagonfs_close(ctx.fds,i);
    state.ops=&hexagonfs_mapped_ops;
    void *invalid_data=NULL;
    assert(hexagonfs_mapped_or_empty_ops.from_dirent(root,false,O_WRONLY|O_TRUNC,&invalid_data)==-EROFS);
    ctx.rootfd=hexagonfs_open_root(ctx.fds,&state);
    assert(hexagonfs_openat_mode(ctx.fds,ctx.rootfd,ctx.rootfd,"sns_reg_version",O_WRONLY|O_TRUNC)==-EROFS);
    assert(file_mode("rb+")==O_RDWR && file_mode("ab")== (O_WRONLY|O_CREAT|O_APPEND));
    assert(file_mode("r++")==-EINVAL);
    hexagonfs_close(ctx.fds,ctx.rootfd);
    snprintf(path,sizeof(path),"%s/link",root);unlink(path);
    snprintf(path,sizeof(path),"%s/new",root);unlink(path);
    snprintf(path,sizeof(path),"%s/sns_reg_version",root);unlink(path);rmdir(root);
    puts("PASS: file open/write/rename/read, stdio modes, readonly rejection, symlink rejection");
}
