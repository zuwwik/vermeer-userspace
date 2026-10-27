#include <assert.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include "hexagonrpcd/hexagonfs.h"
#include "hexagonrpcd/rpcd_builder.h"
int main(int argc,char **argv)
{
    assert(argc==2);
    struct hexagonfs_fd *fds[HEXAGONFS_MAX_FD]={0};
    int root=hexagonfs_open_root(fds,construct_root_dir(argv[1],"adsp"));
    assert(root>=0);
    const char *files[]={"/mnt/vendor/persist/sensors/registry/registry/../sns_reg_version",
        "/sys/devices/soc0/hw_platform","/sys/devices/soc0/platform_version",
        "/sys/devices/soc0/platform_subtype","/sys/devices/soc0/platform_subtype_id",
        "/vendor/etc/sensors/sns_reg_config",
        "/mnt/vendor/persist/sensors/registry/registry/sensors_registry"};
    for(unsigned i=0;i<sizeof(files)/sizeof(*files);i++) {
        int fd=hexagonfs_openat(fds,root,root,files[i]);
        if(fd<0){fprintf(stderr,"Missing %s: %d\n",files[i],fd);return 1;}
        char value[64]={0};ssize_t bytes=hexagonfs_read(fds,fd,sizeof(value)-1,value);
        printf("READ %s: %zd bytes\n",files[i],bytes);
        assert(bytes>=0 && (bytes>0 || i==6));hexagonfs_close(fds,fd);
    }
    int dir=hexagonfs_openat(fds,root,root,"/odm/etc/sensors/config/");
    assert(dir>=0);char name[256];int count=0;
    while(hexagonfs_readdir(fds,dir,sizeof(name),name)==0 && *name)count++;
    assert(count>10);hexagonfs_close(fds,dir);
    const char *file="/mnt/vendor/persist/sensors/registry/.linux-write-test";
    int fd=hexagonfs_openat_mode(fds,root,root,file,O_WRONLY|O_CREAT|O_TRUNC);
    assert(fd>=0 && hexagonfs_write(fds,fd,3,"ok\n")==3);hexagonfs_close(fds,fd);
    fd=hexagonfs_openat(fds,root,root,file);
    char value[3];assert(fd>=0 && hexagonfs_read(fds,fd,3,value)==3 && !memcmp(value,"ok\n",3));
    for(int i=0;i<HEXAGONFS_MAX_FD;i++)if(fds[i])hexagonfs_close(fds,i);
    puts("PASS: registry parent/version, socinfo, ODM configs, private registry write/read");
}
