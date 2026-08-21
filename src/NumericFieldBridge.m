//
//  NumericFieldBridge.m
//  gomapp
//
//  Created by Kiri Daust on 2026-08-06.
//

#import <UIKit/UIKit.h>
#import "NumericFieldBridge.h"

@interface NumericFieldBridge ()

@property (nonatomic, assign) CGRect normalFrame;
@property (nonatomic, assign) BOOL keyboardAdjusted;

- (void)keyboardWillChangeFrame:(NSNotification *)notification;
- (void)keyboardWillHide:(NSNotification *)notification;

@end

@implementation NumericFieldBridge

- (instancetype)initDecimal:(BOOL)decimal
{
    NSLog(@"NumericFieldBridge initDecimal");
    self = [super initWithFrame:CGRectZero];
    
    if (self)
    {
        _textField = [[UITextField alloc] initWithFrame:self.bounds];
        
        _textField.delegate = self;
        
        _textField.autoresizingMask =
        UIViewAutoresizingFlexibleWidth |
        UIViewAutoresizingFlexibleHeight;
        
        _textField.borderStyle = UITextBorderStyleRoundedRect;
        
        _textField.clearButtonMode =
        UITextFieldViewModeWhileEditing;
        
        _textField.returnKeyType =
        UIReturnKeyDone;
        
        if (decimal)
        {
            _textField.keyboardType =
            UIKeyboardTypeDecimalPad;
        }
        else
        {
            _textField.keyboardType =
            UIKeyboardTypeNumberPad;
        }
        UIToolbar *toolbar = [[UIToolbar alloc] init];
        [toolbar sizeToFit];

        UIBarButtonItem *flex =
        [[UIBarButtonItem alloc]
         initWithBarButtonSystemItem:UIBarButtonSystemItemFlexibleSpace
         target:nil
         action:nil];

        UIBarButtonItem *done =
        [[UIBarButtonItem alloc]
         initWithBarButtonSystemItem:UIBarButtonSystemItemDone
         target:self
         action:@selector(donePressed)];
        
        [[NSNotificationCenter defaultCenter]
            addObserver:self
               selector:@selector(keyboardWillChangeFrame:)
                   name:UIKeyboardWillChangeFrameNotification
                 object:nil];

        [[NSNotificationCenter defaultCenter]
            addObserver:self
               selector:@selector(keyboardWillHide:)
                   name:UIKeyboardWillHideNotification
                 object:nil];

        toolbar.items = @[flex, done];

        _textField.inputAccessoryView = toolbar;
        
        [self addSubview:_textField];
    }
    NSLog(@"UITextField created");
    return self;
}

- (BOOL)isFirstResponder
{
    return [self.textField isFirstResponder];
}

- (BOOL)isVisible
{
    return self.superview != nil;
}

- (void)donePressed
{
    [self.textField resignFirstResponder];
}

- (NSString *)text
{
    return self.textField.text ?: @"";
}

- (void)setText:(NSString *)text
{
    if (![self.textField.text isEqualToString:text]) {
            self.textField.text = text;
        }
}

- (void)setPlaceholder:(NSString *)placeholder
{
    self.textField.placeholder = placeholder;
}

- (BOOL)becomeFirstResponder
{
    return [self.textField becomeFirstResponder];
}

- (BOOL)resignFirstResponder
{
    return [self.textField resignFirstResponder];
}

- (void)setReadOnly:(BOOL)readOnly
{
    self.textField.userInteractionEnabled = !readOnly;

    if (readOnly)
    {
        [self.textField resignFirstResponder];
    }
}

- (void)setFrameX:(CGFloat)x
                y:(CGFloat)y
            width:(CGFloat)width
           height:(CGFloat)height
{
    self.frame = CGRectMake(x, y, width, height);
}

- (void)setKivyFrameX:(CGFloat)x
                    y:(CGFloat)y
                width:(CGFloat)width
               height:(CGFloat)height
{
    // --------------------------------------------------
    // Convert Kivy pixels -> UIKit points
    // --------------------------------------------------

    CGFloat scale = UIScreen.mainScreen.scale;

    x /= scale;
    y /= scale;
    width /= scale;
    height /= scale;

    // --------------------------------------------------
    // Convert Kivy coordinates (origin bottom-left)
    // to UIKit coordinates (origin top-left)
    // --------------------------------------------------

    CGFloat parentHeight = self.bounds.size.height;

    if (self.superview)
    {
        parentHeight = self.superview.bounds.size.height;
    }

    CGFloat uiY = parentHeight - y - height;

    CGRect frame = CGRectMake(
        x,
        uiY,
        width,
        height
    );
    
    self.normalFrame = frame;

    // Only apply Kivy's position directly when the keyboard
    // isn't currently holding the field above it.
    if (!self.keyboardAdjusted)
    {
        self.frame = frame;
    }

    [self setNeedsLayout];

#ifdef DEBUG
//    NSLog(@"Kivy frame -> UIKit frame");
//    NSLog(@"Scale       : %.1f", scale);
//    NSLog(@"Parent      : %.1f", parentHeight);
//    NSLog(@"Kivy        : (%.1f, %.1f) %.1f×%.1f",
//          x * scale,
//          y * scale,
//          width * scale,
//          height * scale);
//    NSLog(@"UIKit       : %@",
//          NSStringFromCGRect(self.frame));
#endif
}

- (void)layoutSubviews
{
    [super layoutSubviews];

    self.textField.frame = self.bounds;
}

- (void)show
{
    NSLog(@"NumericFieldBridge show()");
    UIWindow *window = nil;

    if (@available(iOS 13.0, *)) {
        for (UIScene *scene in UIApplication.sharedApplication.connectedScenes) {

            if ([scene isKindOfClass:[UIWindowScene class]]) {

                UIWindowScene *ws = (UIWindowScene *)scene;

                for (UIWindow *w in ws.windows) {

                    if (w.isKeyWindow) {
                        window = w;
                        break;
                    }
                }
            }

            if (window) break;
        }
    }
    else {
        window = UIApplication.sharedApplication.keyWindow;
    }
    NSLog(@"Window = %@", window);
    NSLog(@"UIScreen scale = %f", UIScreen.mainScreen.scale);
    if (!window)
        return;

    UIView *root = window.rootViewController.view;

    self.frame = CGRectMake(50, 100, 250, 44);
    [root addSubview:self];

    NSLog(@"NumericFieldBridge added to window");
}

- (void)hide
{
    [self removeFromSuperview];
}

- (CGFloat)parentHeight
{
    if (self.superview)
        return self.superview.bounds.size.height;

    return 0;
}

- (void)keyboardWillChangeFrame:(NSNotification *)notification
{
    // Only move this field if it is the active editor.
    if (![self.textField isFirstResponder])
        return;

    NSDictionary *info = notification.userInfo;

    CGRect keyboardScreenFrame =
        [info[UIKeyboardFrameEndUserInfoKey] CGRectValue];

    // Convert keyboard frame into the same coordinate system
    // as NumericFieldBridge.
    CGRect keyboardFrame =
        [self.superview convertRect:keyboardScreenFrame
                           fromView:nil];

    // Give the field a little breathing room above the keyboard.
    CGFloat padding = -2.0;

    CGFloat fieldBottom = CGRectGetMaxY(self.normalFrame);
    CGFloat keyboardTop = CGRectGetMinY(keyboardFrame);

    CGFloat overlap =
        fieldBottom + padding - keyboardTop;

    if (overlap <= 0)
    {
        self.keyboardAdjusted = NO;
        self.frame = self.normalFrame;
        return;
    }

    CGRect adjustedFrame = self.normalFrame;

    adjustedFrame.origin.y -= overlap;

    self.keyboardAdjusted = YES;

    // Match the keyboard's native animation.
    NSTimeInterval duration =
        [info[UIKeyboardAnimationDurationUserInfoKey] doubleValue];

    UIViewAnimationCurve curve =
        [info[UIKeyboardAnimationCurveUserInfoKey] integerValue];

    UIViewAnimationOptions options =
        (UIViewAnimationOptions)(curve << 16);

    [UIView animateWithDuration:duration
                          delay:0
                        options:options
                     animations:^{
                         self.frame = adjustedFrame;
                     }
                     completion:nil];
}

- (void)keyboardWillHide:(NSNotification *)notification
{
    if (!self.keyboardAdjusted)
        return;

    NSDictionary *info = notification.userInfo;

    NSTimeInterval duration =
        [info[UIKeyboardAnimationDurationUserInfoKey] doubleValue];

    UIViewAnimationCurve curve =
        [info[UIKeyboardAnimationCurveUserInfoKey] integerValue];

    UIViewAnimationOptions options =
        (UIViewAnimationOptions)(curve << 16);

    self.keyboardAdjusted = NO;

    [UIView animateWithDuration:duration
                          delay:0
                        options:options
                     animations:^{
                         self.frame = self.normalFrame;
                     }
                     completion:nil];
}

- (void)dealloc
{
    [[NSNotificationCenter defaultCenter]
        removeObserver:self];
    [super dealloc];
}

@end
