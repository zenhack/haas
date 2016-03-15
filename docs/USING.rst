Using HaaS as a Client
======================

Interaction with HaaS occurs via its REST API. The high-level semantics of the
API are documented in `apidesc.md <apidesc.md>`_, and the mapping to HTTP is
described in `rest_api.md <rest_api.md>`_.

The ``haas`` command line tool is a wrapper around this API. Running ``haas
help`` will display an overview of the available commands. To tell ``haas``
which HaaS instance to use, be sure to do one of:

1. Set the ``HAAS_ENDPOINT`` environmental variable. An example (using
   the default port used when running ``haas serve``) would be ``http://127.0.0.1:5000``
2. Ensure that there is a ``haas.cfg`` in the current directory which contains
   a valid ``client`` section. A valid config file in this case could look
   like

::

   [client]
   endpoint = http://127.0.0.1:5000

* If both configuration methods are present, the ``HAAS_ENDPOINT`` environmental variable will take precedence over whatever is contained within ``haas.cfg``.
* Though insignificant in some circumstances, the presence or absence of trailing slashes within the endpoint URL can cause issues in communicating with the HaaS server, such as "404" errors. For example, using ``http://127.0.0.1:5000`` vs ``http://127.0.0.1:5000/``.

If using the basic auth/database auth backend, you must set the environment
variables ``HAAS_USERNAME`` and ``HAAS_PASSWORD`` to the correct credentials.

Deploying Machines
------------------

The most basic workflow for deploying machines onto a set of nodes allocated
with HaaS is as follows. First, create a headnode, and attach it to the network
that the hardware nodes PXE boot off of.  Then, enter the headnode by VNCing to
it from the headnode host. The VNC port can be found with the REST
``show_headnode`` call. Authentication support `is slated
<https://github.com/CCI-MOC/haas/issues/352>`_ for a future release. From
there, you can set up SSH access to the headnode, or you can continue to use
VNC if you prefer.

Next, configure DHCP and TFTP servers that will boot nodes into some automated
install image.  We have an example of this in ``examples/puppet_headnode``.  In
this example, we use Kickstart to automate a Centos install.  Our kickstart
file configures very little of the system, but complicated configuration can be
done this way, especially by using Kickstart to install a tool such as Puppet.

Our setup has one additional trick.  We run a server that, firstly, serves the
Kickstart file, but secondly makes it so each node only PXE boots the installer
once.  The last thing each node does while installing is to tell the server to
delete its symlink from the TFTP config, which will make the machine fall back
to hard-disk booting the installed system.

This is, as the filepath states, merely an example of how you might deploy to
physical nodes.  Existing deployment systems such as Canonical's MAAS have also
been run succesfully.


Usage Examples
=================

Included herewith are some examples about using cli and api calls. 



1) Register a switch with HaaS:
-------------------------------

Eg> Switch name: mockswitch01
     Host name:  switchhost01
     User name:  switchuser01
     Password:   password1234

api call

::

    curl -X put http://127.0.0.1:5000/switch/mockswitch01 -d '
        {"type": "http://schema.massopencloud.org/haas/v0/switches/mock",
        "hostname": "switchhost01",
        "username": "switchuser01",
        "password": "password1234"}'

cli call

::

       haas switch_register mockswitch02 mock switchhost01 switchuser01 password1234

 
2) Registering a Node which uses IPMI for out of band management
-------------------------------------------------------------


   - **Node name:**  dummyNoderHaaS-02
   - **Ipmi info:**
      + **hostname:**           ipmiHost4node-02
      + **ipmi_username:**      ipmiUser4node-02
      + **ipmi_password:**      ipmiPass4node-02

For nodes using IPMI use the following api call:


::

   curl -X PUT http://127.0.0.1:5001/node/dummyNode01 -d '
   > {"obm": { "type": "http://schema.massopencloud.org/haas/v0/obm/ipmi",
   > "host": "ipmiHost4node-01",
   > "user": "ipmiUser4node-01",
   > "password": "ipmiPass4node-01"
   > }}'

Corresponding cli calls will be as follows:


::

        haas node_register ipmi dummyNode01 ipmiHost4node-01 ipmiUser4node-01 ipmiPass4node-01



