# arbiterdoom
psDooM but where the processes belong to bad users detected by [Arbiter](https://gitlab.chpc.utah.edu/arbiter2/arbiter2). Built using [psdoom-ng](https://github.com/orsonteodoro/psdoom-ng).

## Installation

Install requirements (gcc, make, libsdl2, libsdl2-net, libsdl-mixer, python-imaging):

```bash
apt install gcc make libsdl2-dev libsdl2-net-dev libsdl2-mixer-dev python-imaging
```

Build psdoom-ng (based on [chocolate-doom](https://www.chocolate-doom.org/wiki/index.php/Building_Chocolate_Doom_on_Linux)):

```bash
cd psdoom-ng1
./autogen.sh
export PREFIX=/usr/local
./configure --prefix ${PREFIX}
make
make install
# Install custom psdoom levels
mkdir -p $PREFIX/games/doom
tar xf contrib/psdoom-2000.05.03-data.tar.gz -C ${PREFIX}/share/games/doom
mv ${PREFIX}/share/games/doom/psdoom-data/*.wad ${PREFIX}/share/games/doom
rm -rf ${PREFIX}/share/games/doom/psdoom-data/
DESTDIR=${PREFIX} make install
cp ../freedm.wad ${PREFIX}/share/games/doom
```

