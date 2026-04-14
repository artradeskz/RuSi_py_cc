/* ============================================================
 * Русские аналоги функций вывода
 * ============================================================ */


/* принт - аналог sys_write */
int печать(int fd, char *buf, int count) {
    return __syscall(1, fd, buf, count, 0, 0);
}

/* Syscall wrappers */
int sys_read(int fd, char *buf, int count) {
    return __syscall(0, fd, buf, count, 0, 0);
}


/* длина_строки - аналог strlen */
int длина_строки(char *s) {
    int n = 0;
    while (*s) { n += 1; s = s + 1; }
    return n;
}

/* ============================================================
 * Mini-libc: syscall-only C library for x86-64 Linux
 * ============================================================ */

/* Syscall wrappers */
int sys_read(int fd, char *buf, int count) {
    return __syscall(0, fd, buf, count, 0, 0);
}

int sys_write(int fd, char *buf, int count) {
    return __syscall(1, fd, buf, count, 0, 0);
}

int sys_open(char *path, int flags, int mode) {
    return __syscall(2, (long)path, flags, mode, 0, 0);
}

int sys_close(int fd) {
    return __syscall(3, fd, 0, 0, 0, 0);
}

int sys_brk(int addr) {
    return __syscall(12, addr, 0, 0, 0, 0);
}

int sys_pipe(int *fds) {
    return __syscall(22, (long)fds, 0, 0, 0, 0);
}

int sys_dup2(int oldfd, int newfd) {
    return __syscall(33, oldfd, newfd, 0, 0, 0);
}

int sys_fork() {
    return __syscall(57, 0, 0, 0, 0, 0);
}

int sys_execve(char *path, char **argv, char **envp) {
    return __syscall(59, (long)path, (long)argv, (long)envp, 0, 0);
}

int sys_exit(int code) {
    return __syscall(60, code, 0, 0, 0, 0);
}

int sys_wait4(int pid, int *status, int options, int rusage) {
    return __syscall(61, pid, (long)status, options, rusage, 0);
}

int sys_getcwd(char *buf, int size) {
    return __syscall(79, (long)buf, size, 0, 0, 0);
}

int sys_chdir(char *path) {
    return __syscall(80, (long)path, 0, 0, 0, 0);
}
