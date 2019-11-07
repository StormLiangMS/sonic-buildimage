# Class to handle Elf images
# Placed under GNU Public License by Ken Yap, December 2000

package Elf;

use strict;
use IO::Seekable;

use constant;
use constant TFTPBLOCKSIZE => 512;
# ELF magic header in first 4 bytes
use constant MAGIC => "\x7FELF";
# This is defined by the bootrom layout
use constant HEADERSIZE => 512;
# Size of ELF header
use constant ELF_HDR_LEN => 52;
# Type code
use constant ELFCLASS32 => 1;
# Byte order
use constant ELFDATA2LSB => 1;
# ELF version
use constant EV_CURRENT => 1;
# File type
use constant ET_EXEC => 2;
# Machine type
use constant EM_386 => 3;
# Size of each program header
use constant PROG_HDR_LEN => 32;
# Type of header
use constant PT_LOAD => 1;
# Size of each section header (there is just one)
use constant SECT_HDR_LEN => 40;

use vars qw($libdir $bootseg $bootoff @segdescs $offset);

sub new {
	my $class = shift;
	$libdir = shift;
	my $self = {};
	bless $self, $class;
#	$self->_initialize();
	return $self;
}

sub add_pm_header ($$$$$)
{
	my ($class, $vendorinfo, $headerseg, $bootaddr, $progreturns) = @_;

	push(@segdescs, pack('A4C4@16v2V5v6',
		MAGIC, ELFCLASS32, ELFDATA2LSB, EV_CURRENT,
		255,		# embedded ABI
		ET_EXEC,	# e_type
		EM_386, 	# e_machine
		EV_CURRENT,	# e_version
		$bootaddr,	# e_entry
		ELF_HDR_LEN,	# e_phoff
		0,		# e_shoff (come back and patch this)
		($progreturns ? 0x8000000 : 0),		# e_flags
		ELF_HDR_LEN,	# e_ehsize
		PROG_HDR_LEN,	# e_phentsize
		0,		# e_phnum (come back and patch this)
		SECT_HDR_LEN,	# e_shentsize
		1,		# e_shnum, one mandatory entry 0
		0));		# e_shstrndx
	$offset = HEADERSIZE;
}

# This should not get called as we don't cater for real mode calls but
# is here just in case
sub add_header ($$$$$)
{
	my ($class, $vendorinfo, $headerseg, $bootseg, $bootoff) = @_;

	$class->add_pm_header($vendorinfo, $headerseg, ($bootseg << 4) + $bootoff, 0);
}

sub roundup ($$)
{
# Round up to next multiple of $blocksize, assumes that it's a power of 2
	my ($size, $blocksize) = @_;

	# Default to TFTPBLOCKSIZE if not specified
	$blocksize = TFTPBLOCKSIZE if (!defined($blocksize));
	return ($size + $blocksize - 1) & ~($blocksize - 1);
}

# Grab N bytes from a file
sub peek_file ($$$$)
{
	my ($class, $descriptor, $dataptr, $datalen) = @_;
	my ($file, $fromoff, $status);

	$file = $$descriptor{'file'} if exists $$descriptor{'file'};
	$fromoff = $$descriptor{'fromoff'} if exists $$descriptor{'fromoff'};
	return 0 if !defined($file) or !open(R, "$file");
	binmode(R);
	if (defined($fromoff)) {
		return 0 if !seek(R, $fromoff, SEEK_SET);
	}
	# Read up to $datalen bytes
	$status = read(R, $$dataptr, $datalen);
	close(R);
	return ($status);
}

# Add a segment descriptor from a file or a string
sub add_segment ($$$)
{
	my ($class, $descriptor, $vendorinfo) = @_;
	my ($file, $string, $segment, $len, $maxlen, $fromoff, $align,
		$id, $end, $vilen);

	$end = 0;
	$file = $$descriptor{'file'} if exists $$descriptor{'file'};
	$string = $$descriptor{'string'} if exists $$descriptor{'string'};
	$segment = $$descriptor{'segment'} if exists $$descriptor{'segment'};
	$len = $$descriptor{'len'} if exists $$descriptor{'len'};
	$maxlen = $$descriptor{'maxlen'} if exists $$descriptor{'maxlen'};
	$fromoff = $$descriptor{'fromoff'} if exists $$descriptor{'fromoff'};
	$align = $$descriptor{'align'} if exists $$descriptor{'align'};
	$id = $$descriptor{'id'} if exists $$descriptor{'id'};
	$end = $$descriptor{'end'} if exists $$descriptor{'end'};
	if (!defined($len)) {
		if (defined($string)) {
			$len = length($string);
		} else {
			if (defined($fromoff)) {
				$len = (-s $file) - $fromoff;
			} else {
				$len = -s $file;
			}
			return 0 if !defined($len);		# no such file
		}
	}
	if (defined($align)) {
		$len = &roundup($len, $align);
	} else {
		$len = &roundup($len);
	}
	$maxlen = $len if (!defined($maxlen));
	push(@segdescs, pack('V8',
		PT_LOAD,
		$offset,		# p_offset
		$segment << 4,		# p_vaddr
		$segment << 4,		# p_paddr
		$len,			# p_filesz
		$len,			# p_memsz == p_filesz
		7,			# p_flags == rwx
		TFTPBLOCKSIZE));	# p_align
	$offset += $len;
	return ($len);			# assumes always > 0
}

sub pad_with_nulls ($$)
{
	my ($i, $blocksize) = @_;

	$blocksize = TFTPBLOCKSIZE if (!defined($blocksize));
	# Pad with nulls to next block boundary
	$i %= $blocksize;
	print "\0" x ($blocksize - $i) if ($i != 0);
}

# Copy data from file to stdout
sub copy_file ($$)
{
	my ($class, $descriptor) = @_;
	my ($i, $file, $fromoff, $align, $len, $seglen, $nread, $data, $status);

	$file = $$descriptor{'file'} if exists $$descriptor{'file'};
	$fromoff = $$descriptor{'fromoff'} if exists $$descriptor{'fromoff'};
	$align = $$descriptor{'align'} if exists $$descriptor{'align'};
	$len = $$descriptor{'len'} if exists $$descriptor{'len'};
	return 0 if !open(R, "$file");
	if (defined($fromoff)) {
		return 0 if !seek(R, $fromoff, SEEK_SET);
		$len = (-s $file) - $fromoff if !defined($len);
	} else {
		$len = -s $file if !defined($len);
	}
	binmode(R);
	# Copy file in TFTPBLOCKSIZE chunks
	$nread = 0;
	while ($nread != $len) {
		$status = read(R, $data, TFTPBLOCKSIZE);
		last if (!defined($status) or $status == 0);
		print $data;
		$nread += $status;
	}
	close(R);
	if (defined($align)) {
		&pad_with_nulls($nread, $align);
	} else {
		&pad_with_nulls($nread);
	}
	return ($nread);
}

# Copy data from string to stdout
sub copy_string ($$)
{
	my ($class, $descriptor) = @_;
	my ($i, $string, $len, $align);

	$string = $$descriptor{'string'} if exists $$descriptor{'string'};
	$len = $$descriptor{'len'} if exists $$descriptor{'len'};
	$align = $$descriptor{'align'} if exists $$descriptor{'align'};
	return 0 if !defined($string);
	$len = length($string) if !defined($len);
	print substr($string, 0, $len);
	defined($align) ? &pad_with_nulls($len, $align) : &pad_with_nulls($len);
	return ($len);
}

sub dump_segments
{
	my ($s, $len, $nsegs);

	$nsegs = $#segdescs;	# number of program header entries
	# fill in e_phnum
	substr($segdescs[0], 44, 2) = pack('v', $nsegs);
	# fill in e_shoff to point to a record after program headers
	substr($segdescs[0], 32, 4) = pack('V',
		ELF_HDR_LEN + PROG_HDR_LEN * $nsegs);
	$len = 0;
	while ($s = shift(@segdescs)) {
		$len += length($s);
		print $s;
	}
	# insert section header 0
	# we just need to account for the length, the null fill
	# will create the record we want
	# warn if we have overflowed allocated header area
	print STDERR "Warning, too many segments in file\n"
		if ($len > HEADERSIZE - SECT_HDR_LEN);
	print "\0" x (HEADERSIZE - $len);
}

@segdescs = ();
$offset = 0;	# cumulative offset from beginning of file

1;
