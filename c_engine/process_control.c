#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <limits.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/resource.h>
#include <sys/types.h>
#include <unistd.h>

static int parse_long(const char *s, long *out) {
    char *end = NULL;
    errno = 0;
    long v = strtol(s, &end, 10);
    if (errno || end == s || *end != '\0') return -1;
    *out = v;
    return 0;
}

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "Usage: process_control signal PID TERM|STOP|CONT | priority PID NICE\n");
        return 2;
    }

    long pid_value;
    if (parse_long(argv[2], &pid_value) || pid_value <= 1 || pid_value > INT_MAX) {
        fprintf(stderr, "Invalid PID.\n");
        return 2;
    }
    pid_t pid = (pid_t)pid_value;

    if (strcmp(argv[1], "signal") == 0) {
        if (argc != 4) {
            fprintf(stderr, "Usage: process_control signal PID TERM|STOP|CONT\n");
            return 2;
        }
        int sig;
        if (strcmp(argv[3], "TERM") == 0) sig = SIGTERM;
        else if (strcmp(argv[3], "STOP") == 0) sig = SIGSTOP;
        else if (strcmp(argv[3], "CONT") == 0) sig = SIGCONT;
        else {
            fprintf(stderr, "Unsupported signal. Use TERM, STOP, or CONT.\n");
            return 2;
        }
        if (kill(pid, sig) == -1) {
            perror("kill");
            return 1;
        }
        printf("Signal %s sent to PID %ld.\n", argv[3], pid_value);
        return 0;
    }

    if (strcmp(argv[1], "priority") == 0) {
        if (argc != 4) {
            fprintf(stderr, "Usage: process_control priority PID NICE\n");
            return 2;
        }
        long nice_value;
        if (parse_long(argv[3], &nice_value) || nice_value < -20 || nice_value > 19) {
            fprintf(stderr, "Nice value must be between -20 and 19.\n");
            return 2;
        }
        if (setpriority(PRIO_PROCESS, pid, (int)nice_value) == -1) {
            perror("setpriority");
            return 1;
        }
        errno = 0;
        int actual = getpriority(PRIO_PROCESS, pid);
        if (actual == -1 && errno != 0) {
            perror("getpriority");
            return 1;
        }
        printf("PID %ld nice value is now %d.\n", pid_value, actual);
        return 0;
    }

    fprintf(stderr, "Unknown operation: %s\n", argv[1]);
    return 2;
}
