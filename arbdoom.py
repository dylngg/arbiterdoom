#!/usr/bin/env python3
import argparse
import subprocess
import pick
import shlex
import time
import os
import sys
import pwd
import toml


def die(last_words):
    sys.stderr.write(last_words + " :( \n")
    sys.exit(1)


def main(args):
    status_config = statuses.StatusConfig(
        status_loc=args.database_loc,
        status_table=shared.status_tablename
    )
    user_statuses = statuses.read_status(status_config=status_config)
    bad_uids = []
    for uid, status in user_statuses.items():
        if status.occurrences >= 3:
            bad_uids.append(int(uid))
    if not bad_uids:
        die("There are no bad users on this machine")
        return

    bad_users_list = ["{} ({})".format(pwd.getpwuid(uid).pw_name, pwd.getpwuid(uid).pw_gecos) for uid in bad_uids]
    username_realname, index = pick.pick(bad_users_list, "Which user do you want to kill?", indicator='->')
    bad_uid = bad_uids[index]
    bad_slice = cinfo.UserSlice(bad_uid)
    if not bad_slice.active():
        die(username_realname + " is not alive")

    bad_pids = bad_slice.pids()
    bad_processes = {pid: pidinfo.Process(pid) for pid in bad_pids}
    with open("/tmp/arbdoom-target-procs.txt", 'w') as f:
        for pid, bad_proc in bad_processes.items():
            name = bad_proc.curr_name().strip("()")
            owner_uid = bad_proc.curr_owner(effective_uid=False)
            username = pwd.getpwuid(owner_uid).pw_name
            if owner_uid != bad_uid:
                print("Skipped", name, "since it is not owned by", username_realname)
                continue

            try:
                f.write("{} {} {} 0\n".format(username, pid, name))
            except FileNotFoundError:
                continue
    run(args.arbdoomdir)
    os.remove("/tmp/arbdoom-target-procs.txt")


def command_output(cmd):
    """
    Runs a given bash command and iterates through the lines returned from the
    command. Raises error if there is a problem with the command. Stderror is
    treated as a stdout line.

    cmd: list
        A list with a bash command and it's arguments to be run. See
        subprocess.Popen for format.
    """
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=1,
                            universal_newlines=True, env=os.environ)
    for stdout_line in iter(proc.stdout.readline, ""):
        yield stdout_line

    proc.stdout.close()
    return_code = proc.wait()
    if return_code:
        raise subprocess.CalledProcessError(return_code, cmd)


def run(arbdoomdir):
    if not os.path.exists(arbdoomdir):
        die("{} (-m/--arbdoomdir or $ARBDOOMDIR) does not exist".format(arbdoomdir))

    pscmd = "arbdoom-ps.sh"
    pscmd_path = arbdoomdir + "/" + pscmd
    if not os.path.exists(pscmd_path):
        die("{} (in -m/--arbdoomdir or $ARBDOOMDIR) does not exist".format(pscmd_path))

    killcmd = "arbdoom-kill.sh"
    killcmd_path = arbdoomdir + "/" + killcmd
    if not os.path.exists(killcmd_path):
        die("{} (in -m/--arbdoomdir or $ARBDOOMDIR) does not exist".format(killcmd_path))

    os.environ["DOOMPSCMD"] = pscmd_path
    os.environ["PSDOOMRENICECMD"] = "/bin/true"
    os.environ["PSDOOMKILLCMD"] = killcmd_path
    cmd = ["psdoom-ng", "-episode", "1", "-godstart"]
    for line in command_output(cmd):
        sys.stdout.write(line)


def bootstrap(args):
    """
    Configures the program so that it can function correctly. This is done by
    changing into the arbiter directory and then importing arbiter functions.
    """
    # Make the path to files absolute. This makes behavior consistent when
    # changing directories. Otherwise, configuration files would be relative to
    # the arbiter/ directory
    args.configs = [os.path.abspath(path) for path in args.configs]
    os.chdir(args.arbdir)
    insert(args.arbdir)
    import cfgparser
    try:
        if not cfgparser.load_config(*args.configs, pedantic=False):
            print("There was an issue with the specified configuration (see "
                  "above). You can investigate this with the cfgparser.py "
                  "tool.")
            sys.exit(2)
        args.database_loc = cfgparser.cfg.database.log_location + "/" + cfgparser.shared.statusdb_name
    except (TypeError, toml.decoder.TomlDecodeError) as err:
        print("Configuration error:", str(err), file=sys.stderr)
        sys.exit(2)


def insert(context):
    """
    Appends a path to into the python path.
    """
    context_path = os.path.dirname(__file__)
    sys.path.insert(0, os.path.abspath(os.path.join(context_path, context)))


def arbiter_environ():
    """
    Returns a dictionary with the ARB environment variables. If a variable is
    not found, it is not in the dictionary.
    """
    env = {}
    env_vars = {
        "ARBETC": ("-e", "--etc"),
        "ARBDIR": ("-a", "--arbdir"),
        "ARBDOOMDIR": ("-d", "--arbdoomdir"),
        "ARBCONFIG": ("-g", "--config"),
    }
    for env_name, ignored_prefixes in env_vars.items():
        env_value = os.environ.get(env_name)
        if not env_value:
            continue
        warn = lambda i, s: print("{} in {} {}".format(i, env_name, s))
        expanded_path = lambda p: os.path.expandvars(os.path.expanduser(p))

        for prefix in ignored_prefixes:
            if env_value.startswith(prefix):
                env_value = env_value.lstrip(prefix).lstrip()
                break

        if env_name == "ARBCONFIG":
            config_paths = shlex.split(env_value, comments=False, posix=True)
            valid_paths = []
            for path in config_paths:
                if not os.path.isfile(expanded_path(path)):
                    warn(path, "does not exist")
                    continue
                valid_paths.append(path)

            if valid_paths:
                env[env_name] = valid_paths
            continue

        expanded_value = expanded_path(env_value)
        if not os.path.exists(expanded_value):
            warn(env_value, "does not exist")
            continue
        if not os.path.isdir(expanded_value):
            warn(env_value, "is not a directory")
            continue
        if env_name == "ARBDIR" and not os.path.exists(expanded_value + "/arbiter.py"):
            warn(env_value, "does not contain arbiter modules! (not arbiter/ ?)")
            continue
        if env_name == "ARBETC" and not os.path.exists(expanded_value + "/integrations.py"):
            warn(env_value, "does not contain etc modules! (no integrations.py)")
            continue
        if env_name == "ARBDOOMDIR" and not os.path.exists(expanded_value + "/arbdoom-ps.sh"):
            warn(env_value, "does not contain arbdoom-ps.sh!")
            continue
        if env_name == "ARBDOOMDIR" and not os.path.exists(expanded_value + "/arbdoom-kill.sh"):
            warn(env_value, "does not contain arbdoom-kill.sh!")
            continue
        env[env_name] = expanded_value
    return env


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initializes arbdoom!")
    arb_environ = arbiter_environ()
    parser.add_argument("-a", "--arbdir",
                        type=str,
                        help="Sets the directory in which arbiter modules "
                             "are loaded from. Defaults to $ARBDIR if "
                             "present or ../arbiter otherwise.",
                        default=arb_environ.get("ARBDIR", "../arbiter"),
                        dest="arbdir")
    parser.add_argument("-g", "--config",
                        type=str,
                        nargs="+",
                        help="The configuration files to use to find "
                             "statusdb. Configs will be cascaded together "
                             "starting at the leftmost (the primary config) "
                             "going right (the overwriting configs). "
                             "Defaults to $ARBCONFIG if present or "
                             "../etc/config.toml otherwise.",
                        default=arb_environ.get("ARBCONFIG", ["../etc/config.toml"]),
                        dest="configs")
    parser.add_argument("-m", "--arbdoomdir",
                        type=str,
                        help="Sets the directory in which the arbiterdoom "
                             "scripts are loaded from. Defaults to "
                             "$ARBDOOMDIR if present or "
                             "~/.psdoom-ng/arbiterdoom otherwise.",
                        default=arb_environ.get(
                            "ARBDOOMDIR",
                            os.path.expanduser("~/.psdoom-ng/arbiterdoom")
                        ),
                        dest="arbdoomdir")
    args = parser.parse_args()
    bootstrap(args)
    import statuses
    from cfgparser import shared, cfg
    import cinfo
    import pidinfo
    main(args)
