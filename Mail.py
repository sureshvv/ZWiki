# MailSupport mixin

import string, re, sys
from string import split,join,find,lower,rfind,atoi,strip,lstrip
from types import *

from I18nSupport import _
from TextFormatter import TextFormatter
from Utils import html_unquote,BLATHER,formattedTraceback,stripList, \
     isIpAddress,isEmailAddress,isUsername
from Defaults import AUTO_UPGRADE, PAGE_METATYPE


class SubscriberManagerMixin:
    """
    This mixin class adds subscriber management to a wiki page (and folder).

    Responsibilities: manage a list of subscribers for both this page and
    it's folder, and expose these in the ZMI; also do auto-upgrading.

    A "subscriber" is a string which may be either an email address or a
    CMF member username. A list of these is kept in the page's and/or
    folder's subscriber_list property.

    For the moment, it's still called "email" in arguments to avoid
    breaking legacy dtml (eg subscribeform).
    """
    subscriber_list = []
    _properties=(
        {'id':'subscriber_list', 'type': 'lines', 'mode': 'w'},
        )

    ## private ###########################################################

    def _getSubscribers(self, parent=0):
        """
        Return a copy of this page's subscriber list, as a list.
        
        With parent flag, manage the parent folder's subscriber list instead.
        """
        if AUTO_UPGRADE: self._upgradeSubscribers()
        if parent:
            if hasattr(self.folder(),'subscriber_list'):
                return stripList(self.folder().subscriber_list)
            else:
                return []
        else:
            return list(self.subscriber_list)

    def _setSubscribers(self, subscriberlist, parent=0):
        """
        Set this page's subscriber list. 
        With parent flag, manage the parent folder's subscriber list instead.
        """
        if AUTO_UPGRADE: self._upgradeSubscribers()
        if parent:
            self.folder().subscriber_list = subscriberlist
        else:
            self.subscriber_list = subscriberlist

    def _resetSubscribers(self, parent=0):
        """
        Clear this page's subscriber list.
        With parent flag, manage the parent folder's subscriber list instead.
        """
        self._setSubscribers([],parent)

    def _upgradeSubscribers(self):
        """
        Upgrade old subscriber lists, both this page's and the folder's.

        Called as needed, ie on each access and also from ZWikiPage.upgrade()
        (set AUTO_UPGRADE=0 in Default.py to disable).
        
        XXX Lord have mercy! couldn't this be simpler
        """
        # upgrade the folder first; we'll check attributes then properties
        changed = 0
        f = self.folder().aq_base

        # migrate an old zwiki subscribers or wikifornow _subscribers attribute
        oldsubs = None
        if (hasattr(f, 'subscribers') and
            type(f.subscribers) is StringType):
            if f.subscribers:
                oldsubs = split(re.sub(r'[ \t]+',r'',f.subscribers),',')
            try:
                del f.subscribers
            except KeyError:
                BLATHER('failed to delete self.folder().subscribers')
            changed = 1
        elif hasattr(f, '_subscribers'):
            oldsubs = f._subscribers.keys()
            try:
                del f._subscribers
            except KeyError:
                BLATHER('failed to delete self.folder()._subscribers')
            changed = 1
        # ensure a subscriber_list attribute
        if not hasattr(f, 'subscriber_list'): f.subscriber_list = []
        # transfer old subscribers to subscriber_list, unless it's already
        # populated in which case discard them
        if oldsubs and not f.subscriber_list: f.subscriber_list = oldsubs

        # update _properties
        props = map(lambda x:x['id'], f._properties)
        if 'subscribers' in props:
            f._properties = filter(lambda x:x['id'] != 'subscribers',
                                   f._properties)
            changed = 1
        if not 'subscriber_list' in props:
            f._properties = f._properties + \
                ({'id':'subscriber_list','type':'lines','mode':'w'},)

        if changed:
            BLATHER('upgraded %s folder subscriber list' % (f.id))

        # now do the page..
        changed = 0
        self = self.aq_base

        # migrate an old zwiki subscribers attribute
        oldsubs = None
        if (hasattr(self, 'subscribers') and
            type(self.subscribers) is StringType):
            if self.subscribers:
                oldsubs = split(re.sub(r'[ \t]+',r'',self.subscribers),',')
            try:
                del self.subscribers
            except KeyError:
                BLATHER('failed to delete %s.subscribers' % (self.id()))
            changed = 1
        # copy old subscribers to subscriber_list, unless it's already
        # got some
        # XXX merge instead
        if oldsubs and not self.subscriber_list:
            self.subscriber_list = oldsubs

        # migrate a wikifornow _subscribers attribute
        oldsubs = None
        if hasattr(self, '_subscribers'):
            oldsubs = self._subscribers.keys()
            try:
                del self._subscribers
            except KeyError:
                BLATHER('failed to delete %s._subscribers' % (self.id()))
            changed = 1
        if oldsubs and not self.subscriber_list:
            self.subscriber_list = oldsubs

        # update _properties
        props = map(lambda x:x['id'], self._properties)
        if 'subscribers' in props:
            self._properties = filter(lambda x:x['id'] != 'subscribers',
                                      self._properties)
            changed = 1
        if not 'subscriber_list' in props:
            self._properties = self._properties + \
                ({'id':'subscriber_list','type':'lines','mode':'w'},)

        if changed:
            BLATHER('upgraded %s subscriber list' % (self.id()))

    ## page subscription api #############################################

    def subscriberList(self, parent=0):
        """
        Return a list of this page's subscribers
        With parent flag, manage the parent folder's subscriber list instead.
        """
        return self._getSubscribers(parent)

    def subscriberCount(self, parent=0):
        """
        Return the number of subscribers currently subscribed to this page
        With parent flag, count the parent folder's subscriber list
        instead.
        """
        return len(self.subscriberList(parent))

    def isSubscriber(self,email,parent=0):
        """
        Is this email address or member id subscribed to this page ?

        With parent flag, check the parent folder's subscriber list
        instead.  Note "email" may be either an email address
        (case-insensitive) or a CMF member id.  We'll accept either, and
        find subscriptions using either.
        """
        subscriber = email
        if subscriber:
            email = self.emailAddressFrom(subscriber)
            if email: email = string.lower(email)
            usernames = self.usernamesFrom(subscriber)
            for sub in self.subscriberList(parent):
                if not sub: continue
                if ((email and (string.lower(sub) == email)) or
                    (usernames and (sub in usernames))):
                    return 1
        return 0
               
    def subscribe(self, email, REQUEST=None, parent=0):
        """
        Add email as a subscriber to this page.  With parent flag, add to
        the parent folder's subscriber list instead.
        """
        subscriber = email
        if subscriber:
            if not self.isSubscriber(subscriber,parent):
                BLATHER('subscribed',subscriber,'to',self.id())
                subs = self._getSubscribers(parent)
                subs.append(subscriber)
                self._setSubscribers(subs,parent)
                if not parent: self.index_object()
        if REQUEST:
            REQUEST.RESPONSE.redirect(
                REQUEST.get('redirectURL',
                            REQUEST['URL1']+'/subscribeform?email='+subscriber))

    def unsubscribe(self, email, REQUEST=None, parent=0):
        """
        Remove email from this page's subscriber list.  With parent
        flag, remove from the parent folder's subscriber list instead.
        Does not attempt to look up the username from an email address
        or vice-versa, so you must unsubscribe the correct one.
        """
        subscriber = email
        if self.isSubscriber(subscriber,parent):
            sl = self.subscriberList(parent)
            for s in sl:
                if string.lower(s) == string.lower(subscriber):
                    BLATHER('unsubscribed',subscriber,'from',self.id())
                    sl.remove(s)
            self._setSubscribers(sl,parent)
            if not parent: self.index_object()
        if REQUEST:
            REQUEST.RESPONSE.redirect(
                REQUEST.get('redirectURL',
                            REQUEST['URL1']+'/subscribeform?email='+subscriber))

    ## folder subscription api ###########################################

    def wikiSubscriberList(self):
        """whole-wiki version of subscriberList"""
        return self.subscriberList(parent=1)

    def wikiSubscriberCount(self):
        """whole-wiki version of subscriberCount"""
        return self.subscriberCount(parent=1)

    def isWikiSubscriber(self,email):
        """whole-wiki version of isSubscriber"""
        return self.isSubscriber(email,parent=1)

    def wikiSubscribe(self, email, REQUEST=None):
        """whole-wiki version of subscribe"""
        return self.subscribe(email,REQUEST,parent=1)

    def wikiUnsubscribe(self, email, REQUEST=None):
        """whole-wiki version of unsubscribe"""
        return self.unsubscribe(email,REQUEST,parent=1)

    ## misc api methods ##################################################

    def subscribeThisUser(self,REQUEST):
        """
        Subscribe the current user to this page.

        We'll use their username if appropriate, otherwise their email
        address cookie.
        """
        if not REQUEST: return
        user = ((self.inCMF() and str(REQUEST.get('AUTHENTICATED_USER'))) or
                REQUEST.cookies.get('email',None))
        if user and not (self.isSubscriber(user) or self.isWikiSubscriber(user)):
            self.subscribe(user)

    def allSubscribers(self):
        """
        Return a list of subscribers to this page or the whole wiki.

        Special case: if this page is named TestPage or SandBox, return
        only the page subscribers. (Only page subscribers will receive
        mail from these pages.)
        """
        subs = []
        subs.extend(self.subscriberList()) # copy, don't reference
        if self.title_or_id() not in ['TestPage','SandBox']: 
            for s in self.wikiSubscriberList():
                if not (s in subs): subs.append(s)
        return subs

    def allSubscriptionsFor(self, email):
        """
        Return the ids of all pages to which a subscriber is subscribed
        ('whole_wiki' indicates a wiki subscription).

        XXX catalog case duplicates isSubscriber code
        """
        subscriber = email
        subscriptions = []
        # subscriber may be an email address or a member id, and
        # they may be subscribed as either
        email = self.emailAddressFrom(subscriber)
        if email: email = string.lower(email)
        usernames = self.usernamesFrom(subscriber)

        if not (email or usernames):
            return []
        if self.isWikiSubscriber(subscriber):
            subscriptions.append('whole_wiki')
        # optimization: try to use catalog for memory efficiency..
        # XXX can we do better - index subscriber_list and search
        # it directly ?
        if self.hasCatalogIndexesMetadata(
            (['meta_type','path'], ['subscriber_list'])):
            pages = self.pages()
            for page in pages:
                for sub in page.subscriber_list:
                    if not sub: continue
                    if ((email and (string.lower(sub) == email)) or
                        (usernames and (sub in usernames))):
                        subscriptions.append(page.id)
        else:
            # poor caching
            for id, page in self.folder().objectItems(spec=PAGE_METATYPE):
                if page.isSubscriber(subscriber):
                    subscriptions.append(id)
        return subscriptions

    def otherPageSubscriptionsFor(self, email):
        """
        Ack, this was too hard in DTML. Return the ids of all pages to
        which a subscriber is subscribed, excluding the current page and
        'whole_wiki'.
        """
        subscriber = email
        subs = self.allSubscriptionsFor(subscriber)
        thispage = self.id()
        if thispage in subs: subs.remove(thispage)
        if 'whole_wiki' in subs: subs.remove('whole_wiki')
        return subs

    def autoSubscriptionEnabled(self):
        if getattr(self,'auto_subscribe',0):
            return 1
        else:
            return 0

    # utilities

    def emailAddressFrom(self,subscriber):
        """
        Convert an email address or CMF member id to an email address.

        If subscriber is an email address, return as-is.

        Otherwise assume it's a member id and if we are in a CMF site
        look up the member's email address.

        Note to avoid a tricky incompatibility with subscribeform &
        useroptions, we handle the special case of a user acquired
        from above who is a non-member but has an email address in
        portal_memberdata all the same. Since we don't know how to get
        hold of this user object, dig out the member data by id which
        is damned ugly, but can't burn any more time on this right now.

        If we can't get an email address, return None.

        """
        if isEmailAddress(subscriber):
            return subscriber
        elif self.inCMF():
            from Products.CMFCore.utils import getToolByName
            mtool = getToolByName(self, 'portal_membership')
            member = mtool.getMemberById(subscriber)
            if not member:
                mdata = getToolByName(self, 'portal_memberdata')
                member = mdata._members.get(subscriber,None)
            return getattr(member,'email',None)
        else:
            return None

    def emailAddressesFrom(self,subscribers):
        """
        Convert a list of subscribers to a list of email addresses.

        Any of these which are usernames for which we can't find an
        address are converted to an obvious bogus address (rather than
        just quietly dropping recipients).
        """
        emails = []
        for s in subscribers:
            e = self.emailAddressFrom(s)
            emails.append(e or 'NO_ADDRESS_FOR_%s' % s)
        return emails

    def usernamesFrom(self,subscriber):
        """
        Convert subscriber to username(s) if needed and return as a list.

        Ie if subscriber is a username, return that username; if
        subscriber is an email address, return the usernames of any CMF
        members with that email address.

        XXX too expensive; on plone.org with 7k members, this maxed out
        cpu for 10 minutes. Refactor.
        
        """
        if isUsername(subscriber):
            return [subscriber]
        else:
            return []
            # XXX plone.org performance issue
            #email = string.lower(subscriber)
            #usernames = []
            #folder = self.folder()
            #try:
            #    for user in folder.portal_membership.listMembers():
            #        member = folder.portal_memberdata.wrapUser(user)
            #        if string.lower(member.email) == email:
            #            usernames.append(member.name)
            #except AttributeError:
            #    pass
            #return usernames
        

class MailSupport:
    """
    This mixin class provides mail-out support and general mail utilities.
    """

    def isMailoutEnabled(self):
        """
        Has mailout been configured ?
        """
        if (hasattr(self,'MailHost') and
            (self.fromProperty() or self.replyToProperty())):
            return 1
        else:
            return 0

    def mailoutPolicy(self):
        """
        Get my mail-out policy - comments or edits ?
        """
        return getattr(self,'mailout_policy','comments')

    #def formatMailout(self, text):
    #    """
    #    Format some text (usually a page diff) for email delivery.
    #
    #    This is supposed to present a diff, but in the most human-readable
    #    and clutter-free way possible, since people may be receiving many
    #    of these. In the case of a simple comment, it should look as if
    #    the comment was just forwarded out.  See
    #    test_formatMailout/testEndToEndCommentFormatting for examples.
    #
    #    """
    #    if not text: return ''
    #    
    #    # try to do some useful formatting
    #    # wrap and fill each paragraph, except indented ones,
    #    # and preserve citation prefixes
    #    paragraphs = stripList(split(text,'\n\n'))
    #    for i in range(len(paragraphs)):
    #        p = paragraphs[i]
    #        indent = len(p) - len(lstrip(p))
    #        #if indent or p[0] == '>': continue
    #        if indent: continue
    #        m = re.match(r'^[>\s]+',p)
    #        if m:
    #            prefix = m.group()
    #            p = re.sub(r'(?m)^'+prefix,'',p)
    #        else:
    #            prefix = ''
    #        # TextFormatter loses a trailing newline
    #        # (and a single leading newline, but that shouldn't apply)
    #        if p[-1] == '\n': nl = '\n'
    #        else: nl = ''
    #        p = TextFormatter([{'width':70-len(prefix),
    #                            'margin':0,
    #                            'fill':1,
    #                            'pad':0}]).compose([p])
    #        p = re.sub(r'(?m)^',prefix,p)
    #        p += nl
    #        paragraphs[i] = p
    #        
    #    text = join(paragraphs,'\n\n')
    #
    #    # strip leading newlines
    #    text = re.sub(r'(?s)^\n+',r'',text)
    #    # strip trailing newlines
    #    text = re.sub(r'(?s)\n+$',r'\n',text)
    #    # lose any html quoting
    #    text = html_unquote(text)
    #    return text

    def sendMailToSubscribers(self, text, REQUEST, subjectSuffix='',
                              subject='',message_id=None,in_reply_to=None,
                              exclude_address=None):
        """
        Send mail to any page subscribers, and log any errors.
        
        If a mailhost and mail_from property have been configured and
        there are subscribers to this page, email text to them.  So as not
        to prevent page edits, catch any mail-sending errors (and log and
        try to forward them to an admin).
        """
        recipients = self.emailAddressesFrom(self.allSubscribers())
	# mailin.py may need to exclude an address to avoid a loop
        try: recipients.remove(exclude_address)
        except ValueError: pass

        if not recipients: return
        
	# some lists will deliver duplicated addresses twice ? try to avoid
        unique = []
        for r in recipients:
            if not r in unique:
                unique.append(r)
        if self.toProperty() in unique: unique.remove(self.toProperty())
        
        # send the mail
        try:
            self.sendMailTo(unique,text,REQUEST,
                            subjectSuffix=subjectSuffix,
                            subject=subject,
                            message_id=message_id,
                            in_reply_to=in_reply_to)
        # if there is any failure, notify admin or log
        except:
            BLATHER('failed to send mail to %s: %s' % (recipients,
                                                       formattedTraceback()))
            admin = getattr(self.folder(),'mail_admin',None)
            if admin:
                try:
                    self.sendMailTo(
                        [],text,REQUEST,
                        subjectSuffix='ERROR, subscriber mailout failed',
                        to=admin)
                except:
                    BLATHER('failed to send error report to admin: %s' % \
                            formattedTraceback())

    def fromProperty(self):
        """
        Give the mail_from property for this page.
        """
        return getattr(self.folder(),'mail_from','')
    
    def replyToProperty(self):
        """
        Give the mail_replyto property for this page.
        """
        return getattr(self.folder(),'mail_replyto','')
    
    def toProperty(self):
        """
        Give the mail_to property for this page.
        """
        return getattr(self.folder(),'mail_to','')
    
    def fromHeader(self,REQUEST=None):
        """
        Give the appropriate From: header for mail-outs from this page.

        Tries to give the best attribution based on configuration and
        available information.  XXX todo: use an authenticated CMF
        member's email property
        """
        address = (self.fromProperty() or
                   self.usersEmailAddress() or
                   self.replyToProperty())
        realname = self.usernameFrom(REQUEST,ip_address=0) or _('anonymous')
        return '%s (%s)' % (address, realname)

    def replyToHeader(self):
        """
        Give the appropriate Reply-to: header for mail-outs from this page.
        """
        return self.replyToProperty() or self.fromProperty()
    
    def listId(self):
        """
        Give the "list id" for mail-outs from this page.
        """
        return self.fromProperty() or self.replyToProperty()
    
    def listPostHeader(self):
        """
        Give the appropriate List-Post: header for mail-outs from this page.
        """
        return '<mailto:%s>' % (self.listId())

    def listIdHeader(self):
        """
        Give the appropriate List-ID: header for mail-outs from this page.
        """
        return '%s <%s>' % (self.folder().title,self.listId())

    def xBeenThereHeader(self):
        """
        Give the appropriate X-Been-There: header for mail-outs from this page.
        """
        return self.listId()

    def bccHeader(self,recipients):
        """
        Give the appropriate Bcc: header for mail-outs from this page.

        Expects a list of recipient addresses.
        """
        return join(stripList(recipients), ', ')

    def subjectHeader(self,subject='',subjectSuffix=''):
        """
        Give the appropriate Subject: header for mail-outs from this page.

        - adds a prefix if configured in mail_subject_prefix;
        - includes page name in brackets unless disabled with mail_page_name
        - appends subjectSuffix if provided
        """
        if getattr(self.folder(),'mail_page_name',1):
            pagename = '[%s] ' % self.title_or_id()
        else:
            pagename = ''
        return (
            strip(getattr(self.folder(),'mail_subject_prefix','')) +
            pagename +
            subject +
            strip(subjectSuffix))

    def toHeader(self):
        """
        Give the appropriate To: header for mail-outs from this page.

        When sending a mail-out, we put the subscribers in Bcc for privacy.
        Something is needed in To, what should we use ?
        1. if there is a mail_to property, use that
        2. if there is a mail_replyto or mail_from property, use that;
           sends a copy back to the wiki which may be the cause of
           conflict-related intermittent slow comments
        3. or use ";" which is a legal "nowhere" but causes messy cc header
           in replies
        """
        return (self.toProperty() or
                self.replyToProperty() or
                self.fromProperty() or
                ';')

    def signature(self, message_id=None):
        """
        Give the appropriate signature to add to mail-outs from this page.

        That is:
        - the contents of the mail_signature property
        - or a semi-permalink to a comment if its message id is provided
        - or a link to this page
        """
        url = self.pageUrl()
        if message_id:
            # sync with makeCommentHeading
            url += '#msg%s' % re.sub(r'^<(.*)>$',r'\1',message_id) 
        return getattr(self.folder(),'mail_signature',
                       '--\nforwarded from %s' % url) # XXX i18n

    def mailhost(self):
        """
        Give the MailHost that should be used for sending mail.
        """
        return self.MailHost

    def sendMailTo(self, recipients, text, REQUEST,
                   subjectSuffix='',
                   subject='',
                   message_id=None,
                   in_reply_to=None,
                   to=None,
                   ):
        """
        Send a mail-out to recipients, if mail properties are configured.

        Tries to provide the best possible headers based on available
        information in arguments, zodb, username cookie etc.

        XXX templatize ?
        XXX mailing list integration issues
        - ezmlm won't deliver precedence: bulk, which these are, what to do
	- ezmlm was delivering duplicates due to duplicate addresses at one point..
          we seem ok now
        """
        if not self.isMailoutEnabled(): return
        msgid = message_id or self.messageIdFromTime(self.ZopeTime())
        msg = """\
From: %s
Reply-To: %s
To: %s
Bcc: %s
Subject: %s
Message-ID: %s%s
X-Zwiki-Version: %s
X-BeenThere: %s
List-Id: %s
List-Post: %s
List-Subscribe: <%s/subscribeform>
List-Unsubscribe: <%s/subscribeform>
List-Archive: <%s>
List-Help: <%s>

%s
%s
""" \
        % (self.fromHeader(REQUEST),
           self.replyToHeader(),
           to or self.toHeader(),
           self.bccHeader(recipients),
           self.subjectHeader(subject,subjectSuffix),
           msgid,
           (in_reply_to and '\nIn-reply-to: %s' % in_reply_to) or '',
           self.zwiki_version(),
           self.xBeenThereHeader(),
           self.listIdHeader(),
           self.listPostHeader(),
           self.pageUrl(),
           self.pageUrl(),
           self.pageUrl(),
           self.wikiUrl(),
           text, #self.formatMailout(text) # IssueNo0696
           self.signature(msgid),
           )

        if subject == '[test]':
            # for testing:
            BLATHER('discarding test mailout:\n%s' % msg)
            #self.sendTestMail()
        else:
            BLATHER('sending mailout:\n%s' % msg)
            self.mailhost().send(msg)
        # XXX experimental
        #self.sendCiaBotMail


#    def sendCiaBotMail(self):
#        """
#        Send mail to an IRC channel via ciabot (or similar).
#
#        This is sent separately so we can provide the special headers.
#        """
#        mail_irc_address = getattr(self.folder(),'mail_irc_address',None)
#        if mail_irc_address:
#            msg = """\
#From: %s
#To: %s
#Subject: %s
#
#%s: %s
#%s
#""" \
#            % (fromhdr,
#               mail_irc_address,
#               getattr(self.folder(),'mail_irc_subject',''),
#               username,
#               body,
#               signature,
#               )
#            self.mailhost().send(msg)
#            BLATHER('sending mailout to IRC:',msg)

#    def sendTestMail(self):
#        """
#        Send a mail which users won't see, but we can monitor in tests
#        """
#        BLATHER('diverting test mailout to test server:\n%s' % msg)
#        # I tried sending to a test SMTP server, but it blocked
#        #try:
#        #    self.TestMailHost.send(msg)
#        #    BLATHER('sent mailout to test server')
#        #    BLATHER('TestMailHost info:',
#        #         self.TestMailHost.smtp_host,
#        #         self.TestMailHost.smtp_port)
#        #except:
#        #    type, val, tb = sys.exc_info()
#        #    err = string.join(
#        #        traceback.format_exception(type,val,tb),'')
#        #    BLATHER('failed to send mailout to test server:',
#        #         err,
#        #         self.TestMailHost.smtp_host,
#        #         self.TestMailHost.smtp_port)
#        # instead, I sent as usual and hacked mailman to drop it
#        # do add a X-No-Archive header
#        msg = re.sub(r'(?m)(List-Help:.*$)',
#                     r'\1\nX-No-Archive: yes',
#                     msg)
#        BLATHER('sending mailout:\n%s' % msg)
#        self.mailhost().send(msg)

#if __name__ == '__main__':
#    import contract, doctest, Mail
#    contract.checkmod(Mail)
#    doctest.testmod(mid)
