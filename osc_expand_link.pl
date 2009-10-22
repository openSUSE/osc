#! /usr/bin/perl -w
#
# osc_expand_link.pl -- a tool to help osc build packages where an _link exists.
# (C) 2006 jw@suse.de, distribute under GPL v2.
#
# 2006-12-12, jw
# 2006-12-15, jw, v0.2 -- {files}{error} gets printed if present.
# 2008-03-25, jw, v0.3 -- go via api using iChains and ~/.oscrc
# 2008-03-26, jw, v0.4 -- added linked file retrieval and usage.
# 2009-10-21, jw,         added obsolete warning, in favour of osc co -e

use Data::Dumper;
use LWP::UserAgent;
use HTTP::Status;
use Digest::MD5;

my $version = '0.4';
my $verbose = 1;

print "This $0 is obsolete. Please use instead: osc co -e\n";
sleep 5;

# curl buildservice:5352/source/home:jnweiger/vim
# curl 'buildservice:5352/source/home:jnweiger/vim?rev=d90bfab4301f758e0d82cf09aa263d37'
# curl 'buildservice:5352/source/home:jnweiger/vim/vim.spec?rev=d90bfab4301f758e0d82cf09aa263d37'

my $cfg = {
  apiurl  => slurp_file(".osc/_apiurl", 1),
  package => slurp_file(".osc/_package", 1),
  project => slurp_file(".osc/_project", 1),
  files   => xml_slurp_file(".osc/_files", { container => 'directory', attr => 'merge' }),
  link   => xml_slurp_file(".osc/_link",   { container => 'link', attr => 'merge' }),
};

{
  package CredUserAgent;
  @ISA = qw(LWP::UserAgent);

  sub new
  {
    my $self = LWP::UserAgent::new(@_);
    $self->agent("osc_expand_link.pl/$version");
    $self;
  }
  sub get_basic_credentials
  {
    my ($self, $realm, $uri) = @_;
    my $netloc = $uri->host_port;

    unless ($self->{auth})
      {
        print STDERR "Auth for $realm at $netloc\n";
        unless (open IN, "<", "$ENV{HOME}/.oscrc")
          {
            print STDERR "$ENV{HOME}/.oscrc: $!\n";
            return (undef, undef);
          }
        while (defined (my $line = <IN>))
          {
            chomp $line;
            $self->{auth}{pass} = $1 if $line =~ m{^pass\s*=\s*(\S+)};
            $self->{auth}{user} = $1 if $line =~ m{^user\s*=\s*(\S+)};
          }
        close IN;
        print STDERR "~/.oscrc: user=$self->{auth}{user}\n";
      }
    return ($self->{auth}{user},$self->{auth}{pass});
  }
}

my $ua = CredUserAgent->new (keep_alive => 1);

sub cred_get
{
  my ($url) = @_;
  my $r = $ua->get($url);
  die "$url: " . $r->status_line . "\n" unless $r->is_success;
  return $r->content;
}

sub cred_getstore
{
  my ($url, $file) = @_;
  my $r = $ua->get($url, ':content_file' => $file);
  die "$url: " . $r->status_line . "\n" unless $r->is_success;
  $r->code;
}

$cfg->{apiurl}  ||= 'https://api.opensuse.org';
$cfg->{project} ||= '<Project>';
$cfg->{package} ||= '<Package>';

chomp $cfg->{apiurl};
chomp $cfg->{project};
chomp $cfg->{package};

my $source = "$cfg->{apiurl}/source";
my $url = "$source/$cfg->{project}/$cfg->{package}";

if (my $url = $ARGV[0])
  {

    die qq{osc_expand_link $version;

Usage:

 osc co $cfg->{project} $cfg->{package}
 cd $cfg->{project}/$cfg->{package}
 $0

to resolve a _link.

or

 $0 $cfg->{apiurl}/source/$cfg->{project}/$cfg->{package}

to review internal buildservice data.

or
 $0 $cfg->{apiurl}/source/$cfg->{project}/$cfg->{package}/linked/\\*.spec

 cd $cfg->{project}/$cfg->{package}
 $0 linked \\*.spec

to retrieve the original specfile behind a link.

} if $url =~ m{^-};

    $url = "$url/$ARGV[1]" if $url eq 'linked' and $ARGV[1];
    if ($url =~ m{^(.*/)?linked/(.*)$})
      {
        $url = (defined $1) ? $1 : "$cfg->{project}/$cfg->{package}";
        my $file = $2;
        $url = "$source/$url" if $cfg->{apiurl} and $url !~ m{://};
        print STDERR "$url\n";
        my $dir = xml_parse(cred_get($url), 'merge');
        my $li = $dir->{directory}{linkinfo} || die "no linkinfo in $url\n";
        $url = "$source/$li->{project}/$li->{package}";
        mkdir("linked");

        if ($file =~ m{\*})
          {
            my $dir = xml_parse(cred_get($url), 'merge');
            $dir = $dir->{directory} if $dir->{directory};
            my @list = sort map { $_->{name} } @{$dir->{entry}};
            my $file_re = "\Q$file\E"; $file_re =~ s{\\\*}{\.\*}g;
            my @match = grep { $_ =~ m{^$file_re$} } @list;
            die "pattern $file not found in\n @list\n" unless @match;
            $file = $match[0];
          }
        $url .= "/$file";

        print STDERR "$url -> linked/$file\n";
        my $r = cred_getstore($url, "linked/$file");
        print STDERR " Error: $r\n" if $r != RC_OK;
        exit 0;
      }

    $url = "$cfg->{project}/$cfg->{package}/$url" unless $url =~ m{/};
    $url = "$source/$url" if $cfg->{apiurl} and $url !~ m{://};
    print cred_get($url);
    exit 0;
  }

warn "$cfg->{project}/$cfg->{package} error: $cfg->{files}{error}\n" if $cfg->{files}{error};
die "$cfg->{project}/$cfg->{package} has no _link\n" unless $cfg->{link};
die "$cfg->{project}/$cfg->{package} has no xsrcmd5\n" unless $cfg->{files}{xsrcmd5};

print STDERR "expanding link to $cfg->{link}{project}/$cfg->{link}{package}\n";
if (my $p = $cfg->{link}{patches})
  {
    $p = [ $p ] if ref $p ne 'ARRAY';
    my @p = map { "$_->{apply}{name}" } @$p;
    print STDERR "applied patches: " . join(',', @p) . "\n";
  }

my $dir = xml_parse(cred_get("$url?rev=$cfg->{files}{xsrcmd5}"), 'merge');
$dir = $dir->{directory} if defined $dir->{directory};
$dir->{entry} = [ $dir->{entry} ] if ref $dir->{entry} ne 'ARRAY';
for my $file (@{$dir->{entry}})
  {
    if (-f $file->{name})
      {
        ## check the md5sum of the existing file and be happy.
        $md5 = Digest::MD5->new;
        open IN, "<", $file->{name} or die "md5sum($file->{name} failed: $!";
        $md5->addfile(*IN);
        close IN;
        if ($md5->hexdigest eq $file->{md5})
          {
            print STDERR " - $file->{name} (md5 unchanged)\n";
          }
        else
          {
            print STDERR "Modified: $file->{name}, please commit changes!\n";
          }
        next;
      }
    print STDERR " get $file->{name}";
    # fixme: xsrcmd5 is obsolete.
    # use <linkinfo project="openSUSE:Factory" package="avrdude" xsrcmd5="a39c2bd14c3ad5dbb82edd7909fcdfc4">
    my $response = cred_getstore("$url/$file->{name}?rev=$cfg->{files}{xsrcmd5}", $file->{name});
    print STDERR ($response == RC_OK) ? "\n" : " Error:$response\n";
  }
exit 0;
##########################################################################

sub slurp_file
{
  my ($path, $silent) = @_;
  open IN, "<", $path or ($silent ? return undef : die "slurp_file($path) failed: $!\n");
  my $body = join '', <IN>;
  close IN;
  return $body;
}


#################################################################
## xml parser imported from w3dcm.pl and somewhat expanded.
## 2006-12-15, jw
##
## xml_parse assumes correct container closing.
## Any </...> tag would closes an open <foo>.
## Thus xml_parse is not suitable for HTML.
##
sub xml_parse
{
  my ($text, $attr) = @_;
  my %xml;
  my @stack = ();
  my $t = \%xml;

#print "xml_parse: '$text'\n";
  my @tags = find_tags($text);
  for my $i (0 .. $#tags)
    {
      my $tag = substr $text, $tags[$i]->{offset}, $tags[$i]->{tag_len};
      my $cdata = '';
      my $s = $tags[$i]->{offset} + $tags[$i]->{tag_len};
      if (defined $tags[$i+1])
        {
          my $l = $tags[$i+1]->{offset} - $s;
          $cdata = substr $text, $s, $l;
        }
      else
        {
          $cdata = substr $text, $s;
        }

#      print "tag=$tag\n";
      my $name = $1 if $tag =~ s{<([\?/]?[\w:-]+)\s*}{};
      $tag =~ s{>\s*$}{};
      my $nest = ($tag =~ s{[\?/]$}{}) ? 0 : 1;
      my $close = ($name =~ s{^/}{}) ? 1 : 0;
#      print "name=$name, attr='$tag', $close, $nest, '$cdata'\n";

      my $x = {};
      $x->{-cdata} .= $cdata if $nest;
      xml_add_attr($x, $tag, $attr) unless $tag eq '';

      if (!$close)
        {
          delete $t->{-cdata} if $t->{-cdata} and $t->{-cdata} =~ m{^\s*$};
          unless ($t->{$name})
            {
              $t->{$name} = $x;
            }
          else
            {
              $t->{$name} = [ $t->{$name} ] unless ref $t->{$name} eq 'ARRAY';
              push @{$t->{$name}}, $x;
            }
        }


      if ($close)
        {
          $t = pop @stack;
        }
      elsif ($nest)
        {
          push @stack, $t;
          $t = $x;
        }
    }

  print "stack=", Data::Dumper::Dumper(\@stack) if $verbose > 2;
  scalar_cdata($t);
  return $t;
}

##
## reads a file formatted by xml_make, and returns a hash.
## The toplevel container is removed from that hash, if specified.
## A wildcard '*' can be specified to remove any toplevel container.
## Otherwise the name of the container must match precisely.
##
sub xml_slurp_file
{
  my ($file, $opt) = @_;
  unless (open IN, "<$file")
    {
      return undef unless $opt->{die};
      die "xml_slurp($opt->{container}): cannot read $file: $!\n";
    }

  my $xml = join '', <IN>; close IN;
  $xml = xml_parse($xml, $opt->{attr});
  if (my $container = $opt->{container})
    {
      die "xml_slurp($file, '$container') malformed file, should have only one toplevel node.\n"
        unless scalar keys %$xml == 1;
      $container = (keys %$xml)[0] if $container eq '' or $container eq '*';
      die "xml_slurp($file, '$container') toplevel tag missing or wrong.\n" unless $xml->{$container};
      $xml = $xml->{$container};
    }
  return $xml;
}

sub xml_escape
{
  my ($text) = @_;

  ## XML::Simple does just that:
  $text =~ s{&}{&amp;}g;
  $text =~ s{<}{&lt;}g;
  $text =~ s{>}{&gt;}g;
  $text =~ s{"}{&quot;}g;
  return $text;
}

sub xml_unescape
{
  my ($text) = @_;

  ## XX: Fimxe: we should handle some more escapes here...
  ## and better do it in a single pass.
  $text =~ s{&#([\d]{3});}{chr $1}eg;
  $text =~ s{&lt;}{<}g;
  $text =~ s{&gt;}{>}g;
  $text =~ s{&quot;}{"}g;
  $text =~ s{&amp;}{&}g;

  return $text;
}

##
## find all hashes, that contain exactly one key named '-cdata'
## and replace these hashes with the value of that key.
## These values are scalar when created by xml_parse(), hence the name.
##
sub scalar_cdata
{
  my ($hash) = @_;
  my $selftag = '.scalar_cdata_running';

  return unless ref $hash eq 'HASH';
  return if $hash->{$selftag};
  $hash->{$selftag} = 1;

  for my $key (keys %$hash)
    {
      my $val = $hash->{$key};
      if (ref $val eq 'ARRAY')
        {
          for my $i (0..$#$val)
            {
              scalar_cdata($hash->{$key}[$i]);
            }
        }
      elsif (ref $val eq 'HASH')
        {
          my @k = keys %$val;
          if (scalar(@k) == 1 && ($k[0] eq '-cdata'))
            {
              $hash->{$key} = $hash->{$key}{-cdata};
            }
          else
            {
              delete $hash->{$key}{-cdata} if exists $val->{-cdata} && $val->{-cdata} =~ m{^\s*$};
              scalar_cdata($hash->{$key});
            }
        }
    }
  delete $hash->{$selftag};
}

##
## find_tags -- a brute force tag finder.
## This code is robust enough to parse the weirdest HTML.
## An Array containing hashes of { offset, name, tag_len } is returned.
## CDATA is skipped, but can be determined from gaps between tags.
## The name parser may chop names, so XML-style tag names are
## unreliable.
##
sub find_tags
{
  my ($text) = @_;
  my $last = '';
  my @tags;
  my $inquotes = 0;
  my $incomment = 0;

  while ($text =~ m{(<!--|-->|"|>|<)(/?\w*)}g)
    {
      my ($offset, $what, $name) = (length $`, $1, $2);

      if ($inquotes)
        {
          $inquotes = 0 if $what eq '"';
          next;
        }

      if ($incomment)
        {
          $incomment = 0 if $what eq '-->';
          next;
        }

      if ($what eq '"')
        {
          $inquotes = 1;
          next;
        }

      if ($what eq '<!--')
        {
          $incomment = 1;
          next;
        }

      next if $what eq $last;        # opening and closing angular brackets are polar.

      if ($what eq '>' and scalar @tags)
        {
          $tags[$#tags]{tag_len} = 1 + $offset - $tags[$#tags]{offset};
        }

      if ($what eq '<')
        {
          push @tags, {name => $name, offset => $offset };
        }

      $last = $what;
    }
  return @tags;
}

##
## how = undef:         defaults to '-attr plain'
## how = '-attr plain': add the attributes as one scalar value to hash-element -attr
## how = '-attr hash':  add the attributes as a hash-ref to hash-element -attr
## how = 'merge':       add the attributes as direct hash elements. (This is irreversible)
##
## attributes are either space-separated, or delimited with '' or "".
sub xml_add_attr
{
  my ($hash, $text, $how) = @_;
  $how = 'plain' unless $how;
  my $tag = '-attr'; $tag = $1 if $how =~ s{^\s*([\w_:-]+)\s+(.*)$}{$2};
  $how = lc $how;

  return $hash->{$tag} = $text if $how eq 'plain';

  if ($how eq 'hash')
    {
      $hash = $hash->{$tag} = {};
      $how = 'merge';
      ## fallthrough
    }
  if ($how eq 'merge')
    {
      while ($text =~ m{([\w_:-]+)\s*=("[^"]*"|'[^']'|\S*)\s*}g)
        {
          my ($key, $val) = ($1, $2);
          $val =~ s{^"(.*)"$}{$1} unless $val =~ s{^'(.*)'$}{$1};
          if (defined($hash->{$key}))
            {
              ## redefinition. promote to array and push.
              $hash->{$key} = [ $hash->{$key} ] unless ref $hash->{$key};
              push @{$hash->{$key}}, $val;
            }
          else
            {
              $hash->{$key} = $val;
            }
        }
      return $hash;
    }
  die "xml_expand_attr: unknown method '$how'\n";
}
